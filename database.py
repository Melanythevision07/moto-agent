import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/finanzas_moto.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabla de Movimientos Financieros
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            tipo TEXT CHECK(tipo IN ('INGRESO', 'GASTO_OPERATIVO', 'GASTO_HORMIGA', 'FONDO_MANTENIMIENTO')) NOT NULL,
            categoria TEXT NOT NULL,
            monto REAL NOT NULL,
            descripcion TEXT,
            fuente_mensaje TEXT CHECK(fuente_mensaje IN ('TEXTO', 'AUDIO')) DEFAULT 'TEXTO'
        )
    """)

    # 2. Tabla de Control de Turnos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inicio DATETIME NOT NULL,
            fin DATETIME,
            horas_totales REAL,
            plataforma_principal TEXT,
            ingreso_bruto REAL DEFAULT 0.0,
            utilidad_neta REAL DEFAULT 0.0
        )
    """)

    # 3. Tabla de Sugerencias del Agente (Human-in-the-Loop)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sugerencias_agente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_generacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            patron_detectado TEXT NOT NULL,
            recomendacion TEXT NOT NULL,
            ahorro_estimado REAL,
            estado_feedback TEXT CHECK(estado_feedback IN ('PENDIENTE', 'APROBADA', 'DESCARTADA')) DEFAULT 'PENDIENTE'
        )
    """)

    conn.commit()
    conn.close()
    print(f"Base de datos inicializada correctamente en: {DB_PATH}")


if __name__ == "__main__":
    init_db()