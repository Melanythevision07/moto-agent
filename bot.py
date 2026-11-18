import os
import discord
from dotenv import load_dotenv
from database import init_db, get_connection
from agent_parser import analizar_mensaje, generar_consejo_ahorro, transcribir_audio
from tools import (
    registrar_movimientos_batch,
    iniciar_turno,
    cerrar_turno,
    obtener_resumen_hoy,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Memoria de conversación por canal
historial_chat = {}


class FeedbackSugerenciaView(discord.ui.View):
    def __init__(self, sugerencia_id: int):
        super().__init__(timeout=None)
        self.sugerencia_id = sugerencia_id

    def _actualizar_estado(self, nuevo_estado: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sugerencias_agente SET estado_feedback = ? WHERE id = ?",
            (nuevo_estado, self.sugerencia_id),
        )
        conn.commit()
        conn.close()

    @discord.ui.button(label="✅ Aplicar sugerencia", style=discord.ButtonStyle.success)
    async def aprobar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._actualizar_estado("APROBADA")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=interaction.message.content + "\n\n🟢 **Estado:** Sugerencia APROBADA por el conductor.",
            view=self,
        )

    @discord.ui.button(label="❌ Descartar", style=discord.ButtonStyle.secondary)
    async def descartar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._actualizar_estado("DESCARTADA")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=interaction.message.content + "\n\n⚪ **Estado:** Sugerencia DESCARTADA por el conductor.",
            view=self,
        )


def ejecutar_analisis_hormiga():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT categoria, descripcion, COUNT(*) as veces, SUM(monto) as total
        FROM movimientos
        WHERE tipo = 'GASTO_HORMIGA'
        GROUP BY categoria, descripcion
        ORDER BY total DESC
        LIMIT 10
        """
    )
    filas = cursor.fetchall()

    if not filas:
        conn.close()
        return None, "🎉 Aún no tienes gastos hormiga registrados para analizar."

    texto_datos = "\n".join(
        [f"- {f['categoria']} ({f['descripcion']}): {f['veces']} veces, total ${f['total']:,.0f} COP" for f in filas]
    )
    consejo = generar_consejo_ahorro(texto_datos)

    cursor.execute(
        """
        INSERT INTO sugerencias_agente (patron_detectado, recomendacion, ahorro_estimado)
        VALUES (?, ?, ?)
        """,
        (consejo["patron_detectado"], consejo["recomendacion"], consejo["ahorro_estimado"]),
    )
    sugerencia_id = cursor.lastrowid
    conn.commit()
    conn.close()

    mensaje = (
        f"💡 **Oportunidad de Optimización Detectada**\n"
        f"• **Patrón:** {consejo['patron_detectado']}\n"
        f"• **Sugerencia:** {consejo['recomendacion']}\n"
        f"• **Ahorro semanal estimado:** ~${consejo['ahorro_estimado']:,.0f} COP\n\n"
        f"*¿Deseas adoptar esta recomendación? (Sujeto a tu revisión):*"
    )
    return sugerencia_id, mensaje


@client.event
async def on_ready():
    init_db()
    print(f"✅ MotoFlow Agent activo en Discord como: {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    texto = message.content.strip()
    fuente = "TEXTO"
    prefijo_voz = ""

    # Detectar si el mensaje trae una nota de voz o archivo de audio adjunto
    if not texto and message.attachments:
        adjunto = message.attachments[0]
        es_audio = (
            (adjunto.content_type and adjunto.content_type.startswith("audio/"))
            or adjunto.filename.lower().endswith((".ogg", ".mp3", ".wav", ".m4a", ".webm"))
        )
        if es_audio:
            async with message.channel.typing():
                try:
                    audio_bytes = await adjunto.read()
                    texto = transcribir_audio(audio_bytes, adjunto.filename)
                    fuente = "VOZ"
                    prefijo_voz = f"🎙️ *Escuché:* \"{texto}\"\n\n"
                except Exception as e:
                    print(f"❌ Error transcribiendo audio: {e}")
                    await message.channel.send("⚠️ No pude entender esa nota de voz. Intenta grabarla de nuevo.")
                    return

    if not texto:
        return

    canal_id = message.channel.id
    if canal_id not in historial_chat:
        historial_chat[canal_id] = []

    async with message.channel.typing():
        try:
            analisis = analizar_mensaje(texto, historial_chat[canal_id])

            if analisis.intencion == "REGISTRAR_MOVIMIENTOS":
                respuesta = registrar_movimientos_batch(analisis.movimientos, fuente=fuente)
                await message.channel.send(prefijo_voz + respuesta)
            elif analisis.intencion == "INICIAR_TURNO":
                respuesta = iniciar_turno(analisis.plataforma)
                await message.channel.send(prefijo_voz + respuesta)
            elif analisis.intencion == "CERRAR_TURNO":
                respuesta = cerrar_turno()
                await message.channel.send(prefijo_voz + respuesta)
            elif analisis.intencion == "CONSULTAR_RESUMEN":
                respuesta = obtener_resumen_hoy()
                await message.channel.send(prefijo_voz + respuesta)
            elif analisis.intencion == "ANALIZAR_GASTOS":
                sug_id, respuesta = ejecutar_analisis_hormiga()
                if sug_id:
                    await message.channel.send(prefijo_voz + respuesta, view=FeedbackSugerenciaView(sug_id))
                else:
                    await message.channel.send(prefijo_voz + respuesta)
            else:
                respuesta = analisis.respuesta_conversacional
                await message.channel.send(prefijo_voz + respuesta)

            # Guardar intercambio en la memoria del canal
            historial_chat[canal_id].append({"role": "user", "content": texto})
            historial_chat[canal_id].append({"role": "assistant", "content": respuesta})
            historial_chat[canal_id] = historial_chat[canal_id][-8:]

        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")
            await message.channel.send(
                "⚠️ Tuve un pequeño fallo procesando ese mensaje. Intenta decírmelo de nuevo."
            )


if __name__ == "__main__":
    client.run(TOKEN)