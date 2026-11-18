import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from database import DB_PATH, init_db

st.set_page_config(page_title="MotoFlow CRM", page_icon="🏍️", layout="wide")
init_db()


def cargar_datos():
    conn = sqlite3.connect(DB_PATH)
    df_mov = pd.read_sql_query("SELECT * FROM movimientos ORDER BY fecha_hora DESC", conn)
    df_turnos = pd.read_sql_query("SELECT * FROM turnos ORDER BY inicio DESC", conn)
    df_sug = pd.read_sql_query("SELECT * FROM sugerencias_agente ORDER BY fecha_generacion DESC", conn)
    conn.close()
    return df_mov, df_turnos, df_sug


st.title("🏍️ MotoFlow — CRM Financiero del Conductor")
st.caption("Control de rentabilidad real, gastos hormiga y fondo de mantenimiento")

if st.button("🔄 Actualizar datos"):
    st.rerun()

df_mov, df_turnos, df_sug = cargar_datos()

if df_mov.empty:
    st.info("Aún no hay movimientos registrados. Escríbele a tu bot en Discord para empezar.")
    st.stop()

# Cálculos de KPIs
ingresos = df_mov[df_mov["tipo"] == "INGRESO"]["monto"].sum()
operativos = df_mov[df_mov["tipo"] == "GASTO_OPERATIVO"]["monto"].sum()
hormiga = df_mov[df_mov["tipo"] == "GASTO_HORMIGA"]["monto"].sum()
mantenimiento = df_mov[df_mov["tipo"] == "FONDO_MANTENIMIENTO"]["monto"].sum()
utilidad_neta = ingresos - (operativos + hormiga + mantenimiento)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📈 Ingreso Bruto", f"${ingresos:,.0f}")
col2.metric("⛽ Operativos", f"-${operativos:,.0f}")
col3.metric("🍔 Gastos Hormiga", f"-${hormiga:,.0f}")
col4.metric("🛡️ Fondo Mant.", f"${mantenimiento:,.0f}")
col5.metric("💰 Utilidad Neta Real", f"${utilidad_neta:,.0f}")

st.divider()

# Gráficos principales
g1, g2 = st.columns(2)

with g1:
    st.subheader("Distribución de Egresos y Reservas")
    df_egresos = df_mov[df_mov["tipo"] != "INGRESO"]
    if not df_egresos.empty:
        fig_donut = px.pie(
            df_egresos,
            values="monto",
            names="tipo",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.write("Sin egresos registrados aún.")

with g2:
    st.subheader("Top Gastos Hormiga")
    df_hormiga = df_mov[df_mov["tipo"] == "GASTO_HORMIGA"]
    if not df_hormiga.empty:
        top_h = df_hormiga.groupby("descripcion", as_index=False)["monto"].sum().sort_values("monto")
        fig_bar = px.bar(top_h, x="monto", y="descripcion", orientation="h", text_auto=True)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.write("¡Excelente! Cero gastos hormiga registrados.")

st.divider()

# Panel Human-in-the-Loop y Tabla de Movimientos
c_izq, c_der = st.columns([1, 1.3])

with c_izq:
    st.subheader("🧠 Sugerencias del Agente (Revisión Humana)")
    if not df_sug.empty:
        st.dataframe(
            df_sug[["fecha_generacion", "patron_detectado", "ahorro_estimado", "estado_feedback"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Pídele al bot en Discord: *'Analiza mis gastos hormiga'* para generar sugerencias.")

with c_der:
    st.subheader("📋 Últimos Movimientos Registrados")
    st.dataframe(
        df_mov[["fecha_hora", "tipo", "categoria", "monto", "descripcion"]],
        use_container_width=True,
        hide_index=True,
    )