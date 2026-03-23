"""
Cerebro_IA — Trade Logger
=========================
Registra cada decisión de trade (aprobado o rechazado) en un CSV
para análisis posterior.

Uso:
    from src.trade_logger import TradeLogger
    logger = TradeLogger()
    logger.registrar(...)
"""

import os
import csv
from datetime import datetime

# Directorio donde se guardan los logs
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trades_log.csv")

CAMPOS = [
    "timestamp_registro",   # Cuándo se registró
    "timestamp_vela",       # Timestamp de la vela señal
    "direccion",            # long / short
    "signal",               # 1 = aprobado, 0 = rechazado
    "reasoning",            # Justificación de Gemini
    "fvg_top",              # Techo del FVG
    "fvg_bottom",           # Base del FVG
    "fvg_size",             # Tamaño del FVG en pts
    "precio_entrada",       # Precio de entrada (close de vela señal)
    "sl",                   # Stop Loss
    "tp",                   # Take Profit
    "riesgo_pts",           # Distancia SL en pts
    "rr_ratio",             # Ratio riesgo:beneficio
    "lotes",                # Tamaño de posición
    "ejecutado",            # True/False (si se mandó al broker)
    "ticket",               # Ticket del broker (si se ejecutó)
    "cooldown_restante",    # Velas de cooldown al momento del trigger
]


class TradeLogger:
    """Registra trades en CSV con append incremental."""

    def __init__(self, log_file=None):
        self.log_file = log_file or LOG_FILE
        self._asegurar_directorio()
        self._asegurar_encabezado()

    def _asegurar_directorio(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _asegurar_encabezado(self):
        """Crea el archivo con encabezado si no existe."""
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CAMPOS)

    def registrar(
        self,
        timestamp_vela,
        direccion,
        signal,
        reasoning,
        fvg_top,
        fvg_bottom,
        precio_entrada=None,
        sl=None,
        tp=None,
        lotes=None,
        ejecutado=False,
        ticket=None,
        cooldown_restante=0,
    ):
        """Agrega una fila al log de trades."""
        fvg_size = round(fvg_top - fvg_bottom, 2)
        riesgo_pts = None
        rr_ratio = None

        if precio_entrada and sl:
            riesgo_pts = round(abs(precio_entrada - sl), 2)
            if riesgo_pts > 0 and tp:
                beneficio_pts = abs(tp - precio_entrada)
                rr_ratio = round(beneficio_pts / riesgo_pts, 2)

        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(timestamp_vela),
            direccion,
            signal,
            reasoning or "",
            round(fvg_top, 2),
            round(fvg_bottom, 2),
            fvg_size,
            round(precio_entrada, 2) if precio_entrada else "",
            round(sl, 2) if sl else "",
            round(tp, 2) if tp else "",
            riesgo_pts or "",
            rr_ratio or "",
            lotes or "",
            ejecutado,
            ticket or "",
            cooldown_restante,
        ]

        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fila)

        estado = "APROBADO" if signal == 1 else "RECHAZADO"
        print(f"   📝 Trade {estado} registrado en log.")
