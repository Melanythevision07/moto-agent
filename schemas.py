from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class MovimientoExtraido(BaseModel):
    tipo: Literal["INGRESO", "GASTO_OPERATIVO", "GASTO_HORMIGA"] = Field(
        description=(
            "INGRESO si es dinero ganado en carreras/domicilios. "
            "GASTO_OPERATIVO si es necesario para operar la moto (gasolina, aceite, datos, lavado, repuestos). "
            "GASTO_HORMIGA si es consumo personal menor o evitable en calle (comida rápida, café, bebidas, snacks, cigarrillos)."
        )
    )
    categoria: str = Field(
        default="Otros",
        description="Categoría corta: Plataforma, Combustible, Mantenimiento, Datos Móviles, Alimentación, Bebidas, Otros.",
    )
    monto: float = Field(
        description="Valor numérico en pesos colombianos (COP) sin puntos ni símbolos."
    )
    descripcion: str = Field(
        default="Movimiento registrado",
        description="Breve detalle de la transacción.",
    )


class ResultadoAnalisis(BaseModel):
    intencion: Literal[
        "REGISTRAR_MOVIMIENTOS",
        "INICIAR_TURNO",
        "CERRAR_TURNO",
        "CONSULTAR_RESUMEN",
        "ANALIZAR_GASTOS",
        "OTRO",
    ] = "OTRO"
    plataforma: Optional[str] = None
    movimientos: List[MovimientoExtraido] = Field(default_factory=list)
    respuesta_conversacional: Optional[str] = Field(
        default="¡Hola! Aquí estoy listo para ayudarte con tus finanzas o charlar. ¿Qué necesitas?"
    )