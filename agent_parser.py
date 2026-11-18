import json
import os
from typing import List, Dict
from dotenv import load_dotenv
from groq import Groq
from schemas import ResultadoAnalisis

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
Eres MotoFlow, un copiloto financiero inteligente, cercano y conversacional para conductores de moto en plataformas en Colombia.
Analiza el mensaje del conductor teniendo en cuenta el historial reciente de la conversación y devuelve SIEMPRE un objeto JSON válido.

Reglas de clasificación:
- Si reporta ganancias o gastos ("hice 30 mil", "eché 12 de gasolina", "me compré un tinto"): intencion = "REGISTRAR_MOVIMIENTOS" y extrae cada movimiento en la lista. ("lucas" o "mil" = x1000).
- Si dice "arranco turno", "empiezo a trabajar": intencion = "INICIAR_TURNO".
- Si dice "cierro turno", "terminé por hoy": intencion = "CERRAR_TURNO".
- Si pregunta cómo va el día o cuánto lleva hoy: intencion = "CONSULTAR_RESUMEN".
- Si pide analizar gastos hormiga o consejos sobre sus gastos registrados: intencion = "ANALIZAR_GASTOS".
- Para saludos ("hola", "qué más", "me llamo..."), preguntas generales sobre motos, finanzas, mantenimiento o charla normal: intencion = "OTRO" y escribe una respuesta útil, natural y amigable en "respuesta_conversacional".

Estructura JSON obligatoria (NUNCA omitas "respuesta_conversacional"):
{
  "intencion": "REGISTRAR_MOVIMIENTOS | INICIAR_TURNO | CERRAR_TURNO | CONSULTAR_RESUMEN | ANALIZAR_GASTOS | OTRO",
  "plataforma": null,
  "movimientos": [],
  "respuesta_conversacional": "Tu respuesta natural aquí"
}
"""


def obtener_modelo_disponible() -> str:
    modelos = client.models.list().data
    preferidos = [
        "llama-3.1-8b-instant",
        "qwen/qwen3-32b",
        "qwen-2.5-32b",
        "gemma2-9b-it",
    ]
    ids_disponibles = [m.id for m in modelos]
    for p in preferidos:
        if p in ids_disponibles:
            return p
    for m_id in ids_disponibles:
        if "whisper" not in m_id and "guard" not in m_id:
            return m_id
    raise RuntimeError("No hay modelos de chat disponibles en tu cuenta de Groq.")


def analizar_mensaje(
    texto_usuario: str, historial: List[Dict[str, str]] = None
) -> ResultadoAnalisis:
    modelo_activo = obtener_modelo_disponible()

    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
    if historial:
        mensajes.extend(historial[-6:])
    mensajes.append({"role": "user", "content": texto_usuario})

    chat_completion = client.chat.completions.create(
        messages=mensajes,
        model=modelo_activo,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw_json = chat_completion.choices[0].message.content
    datos_dict = json.loads(raw_json)

    # Normalizar intención y asegurar valores por defecto para evitar errores de validación
    intencion_raw = str(datos_dict.get("intencion", "OTRO")).upper().strip()
    intenciones_validas = {
        "REGISTRAR_MOVIMIENTOS",
        "INICIAR_TURNO",
        "CERRAR_TURNO",
        "CONSULTAR_RESUMEN",
        "ANALIZAR_GASTOS",
        "OTRO",
    }
    datos_dict["intencion"] = (
        intencion_raw if intencion_raw in intenciones_validas else "OTRO"
    )

    if not isinstance(datos_dict.get("movimientos"), list):
        datos_dict["movimientos"] = []

    if not datos_dict.get("respuesta_conversacional"):
        datos_dict["respuesta_conversacional"] = (
            "¡Dime! ¿En qué te ayudo hoy en la ruta?"
        )

    return ResultadoAnalisis(**datos_dict)


def generar_consejo_ahorro(resumen_hormiga: str) -> dict:
    modelo_activo = obtener_modelo_disponible()
    prompt_analista = """
    Eres un asesor financiero experto en optimizar la rentabilidad de conductores de moto en Colombia.
    Analiza el historial de gastos hormiga del conductor y devuelve un JSON estricto con:
    {
      "patron_detectado": "Resumen corto del hábito de gasto más costoso",
      "recomendacion": "Consejo práctico, empático y realista para reducir ese gasto sin afectar su energía en la vía",
      "ahorro_estimado": 0
    }
    El ahorro_estimado debe ser un número entero en pesos colombianos (COP) proyectado a la semana.
    """
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": prompt_analista},
            {"role": "user", "content": f"Historial de gastos hormiga:\n{resumen_hormiga}"},
        ],
        model=modelo_activo,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(chat_completion.choices[0].message.content)



def transcribir_audio(audio_bytes: bytes, nombre_archivo: str = "nota_voz.ogg") -> str:
    transcripcion = client.audio.transcriptions.create(
        file=(nombre_archivo, audio_bytes),
        model="whisper-large-v3-turbo",
        language="es",
        response_format="text",
    )
    return str(transcripcion).strip()