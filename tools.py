from datetime import datetime
from typing import List
from database import get_connection
from schemas import MovimientoExtraido

# Porcentaje de reserva automática para mantenimiento (5% sobre el ingreso bruto del turno)
PORCENTAJE_MANTENIMIENTO = 0.05


def registrar_movimientos_batch(
    movimientos: List[MovimientoExtraido], fuente: str = "TEXTO"
) -> str:
    if not movimientos:
        return "No detecté ningún monto o movimiento para registrar."

    conn = get_connection()
    cursor = conn.cursor()

    lineas_resumen = []
    balance_transaccion = 0.0
    ahora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for mov in movimientos:
        cursor.execute(
            """
            INSERT INTO movimientos (fecha_hora, tipo, categoria, monto, descripcion, fuente_mensaje)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ahora_local, mov.tipo, mov.categoria, mov.monto, mov.descripcion, fuente),
        )

        if mov.tipo == "INGRESO":
            icono = "📈"
            etiqueta = "Ingreso"
            balance_transaccion += mov.monto
        elif mov.tipo == "GASTO_OPERATIVO":
            icono = "⛽"
            etiqueta = "Gasto Operativo"
            balance_transaccion -= mov.monto
        else:
            icono = "🍔"
            etiqueta = "Gasto Hormiga"
            balance_transaccion -= mov.monto

        lineas_resumen.append(
            f"{icono} **{etiqueta}:** ${mov.monto:,.0f} COP ({mov.categoria} - {mov.descripcion})"
        )

    conn.commit()
    conn.close()

    signo = "+" if balance_transaccion >= 0 else ""
    respuesta = "✦ **Movimientos registrados:**\n" + "\n".join(lineas_resumen)
    respuesta += f"\n💡 **Balance neto de este registro:** {signo}${balance_transaccion:,.0f} COP"
    return respuesta


def iniciar_turno(plataforma: str = None) -> str:
    conn = get_connection()
    cursor = conn.cursor()

    # Verificar si ya hay un turno abierto
    cursor.execute("SELECT id, inicio, plataforma_principal FROM turnos WHERE fin IS NULL")
    turno_activo = cursor.fetchone()

    if turno_activo:
        conn.close()
        plat = turno_activo["plataforma_principal"] or "Multi-app"
        return f"⚠️ Ya tienes un turno activo iniciado el `{turno_activo['inicio']}` ({plat}). Di **'cierro turno'** antes de abrir uno nuevo."

    plat_final = plataforma if plataforma else "Multi-app"
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO turnos (inicio, plataforma_principal)
        VALUES (?, ?)
        """,
        (ahora, plat_final),
    )
    conn.commit()
    conn.close()

    return f"🏍️ **Turno iniciado** en **{plat_final}** a las `{ahora[11:16]}`. ¡Buenas rutas!"


def cerrar_turno() -> str:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM turnos WHERE fin IS NULL ORDER BY id DESC LIMIT 1")
    turno = cursor.fetchone()

    if not turno:
        conn.close()
        return "⚠️ No tienes ningún turno abierto actualmente. Escribe **'arranco turno'** cuando empieces."

    inicio_str = turno["inicio"]
    fin_dt = datetime.now()
    fin_str = fin_dt.strftime("%Y-%m-%d %H:%M:%S")
    inicio_dt = datetime.strptime(inicio_str[:19], "%Y-%m-%d %H:%M:%S")

    horas = max(round((fin_dt - inicio_dt).total_seconds() / 3600, 2), 0.1)

    # Buscar movimientos del turno o del día actual
    hoy_str = fin_dt.strftime("%Y-%m-%d")
    cursor.execute(
        """
        SELECT tipo, COALESCE(SUM(monto), 0) as total
        FROM movimientos
        WHERE fecha_hora >= ? OR DATE(fecha_hora) = ?
        GROUP BY tipo
        """,
        (inicio_str, hoy_str),
    )
    totales = {row["tipo"]: row["total"] for row in cursor.fetchall()}

    ingresos = totales.get("INGRESO", 0.0)
    operativos = totales.get("GASTO_OPERATIVO", 0.0)
    hormiga = totales.get("GASTO_HORMIGA", 0.0)

    # Reserva automática 5% para fondo de mantenimiento
    reserva_mant = round(ingresos * PORCENTAJE_MANTENIMIENTO, 0)
    if reserva_mant > 0:
        cursor.execute(
            """
            INSERT INTO movimientos (fecha_hora, tipo, categoria, monto, descripcion, fuente_mensaje)
            VALUES (?, 'FONDO_MANTENIMIENTO', 'Depreciación Moto', ?, 'Reserva automática 5% cierre de turno', 'TEXTO')
            """,
            (fin_str, reserva_mant),
        )

    utilidad_neta = ingresos - (operativos + hormiga + reserva_mant)
    rentabilidad_hora = utilidad_neta / horas

    cursor.execute(
        """
        UPDATE turnos
        SET fin = ?, horas_totales = ?, ingreso_bruto = ?, utilidad_neta = ?
        WHERE id = ?
        """,
        (fin_str, horas, ingresos, utilidad_neta, turno["id"]),
    )

    conn.commit()
    conn.close()

    return (
        f"⏱️ **Turno Finalizado ({horas} hrs)**\n"
        f"• **Ingreso Bruto:** ${ingresos:,.0f} COP\n"
        f"• **Gastos Operativos:** -${operativos:,.0f} COP\n"
        f"• **Gastos Hormiga:** -${hormiga:,.0f} COP\n"
        f"• **Fondo Mantenimiento (5%):** -${reserva_mant:,.0f} COP\n"
        f"────────────────────\n"
        f"💰 **Utilidad Neta Real:** **${utilidad_neta:,.0f} COP**\n"
        f"🚀 **Rentabilidad por Hora:** **${rentabilidad_hora:,.0f} COP / hora**"
    )


def obtener_resumen_hoy() -> str:
    conn = get_connection()
    cursor = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        """
        SELECT tipo, COALESCE(SUM(monto), 0) as total
        FROM movimientos
        WHERE DATE(fecha_hora) = ?
        GROUP BY tipo
        """,
        (hoy,),
    )
    totales = {row["tipo"]: row["total"] for row in cursor.fetchall()}

    # Saldo histórico acumulado en el fondo de mantenimiento
    cursor.execute(
        "SELECT COALESCE(SUM(monto), 0) as fondo FROM movimientos WHERE tipo = 'FONDO_MANTENIMIENTO'"
    )
    fondo_total = cursor.fetchone()["fondo"]
    conn.close()

    ingresos = totales.get("INGRESO", 0.0)
    operativos = totales.get("GASTO_OPERATIVO", 0.0)
    hormiga = totales.get("GASTO_HORMIGA", 0.0)
    mant_hoy = totales.get("FONDO_MANTENIMIENTO", 0.0)
    neto_hoy = ingresos - (operativos + hormiga + mant_hoy)

    return (
        f"📊 **Resumen Financiero de Hoy ({hoy})**\n"
        f"• 📈 **Ingresos Brutos:** ${ingresos:,.0f} COP\n"
        f"• ⛽ **Gastos Operativos:** -${operativos:,.0f} COP\n"
        f"• 🍔 **Gastos Hormiga:** -${hormiga:,.0f} COP\n"
        f"• 🔧 **Reserva Mantenimiento Hoy:** -${mant_hoy:,.0f} COP\n"
        f"────────────────────\n"
        f"💵 **Ganancia Neta Hoy:** **${neto_hoy:,.0f} COP**\n"
        f"🛡️ **Fondo Mantenimiento Acumulado:** ${fondo_total:,.0f} COP"
    )