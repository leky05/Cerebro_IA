import os
from pathlib import Path

# ==========================================
# CONFIGURACIÓN DE RUTAS DINÁMICAS (CORE)
# ==========================================

# Path(__file__).resolve() obtiene la ruta absoluta de este mismo archivo (config.py).
# .parent.parent retrocede dos niveles para situarse en la carpeta raíz (Cerebro_IA).
ROOT_DIR = Path(__file__).resolve().parent.parent

# Definición de las rutas críticas del ecosistema
CONTEXT_KNOWLEDGE_DIR = ROOT_DIR / "context_knowledge"
DATABASE_DIR = ROOT_DIR / "database"
DATA_INGESTION_DIR = ROOT_DIR / "data_ingestion"
SRC_DIR = ROOT_DIR / "src"

def initialize_environment():
    """
    Verifica y crea la estructura de carpetas necesaria si no existe.
    Esto garantiza que al clonar el repo en otra PC, el entorno se construya solo.
    """
    directories = [
        CONTEXT_KNOWLEDGE_DIR,
        DATABASE_DIR,
        DATA_INGESTION_DIR,
        SRC_DIR / "features",
        SRC_DIR / "ml_engine",
        SRC_DIR / "gemini_agent",
        SRC_DIR / "risk_manager",
        SRC_DIR / "backtester",
        SRC_DIR / "telegram_bot",
        SRC_DIR / "execution_bots"
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        
    print(f"✅ Entorno de rutas inicializado. Raíz detectada en: {ROOT_DIR}")

# Si ejecutamos este script directamente, creará las carpetas faltantes.
if __name__ == "__main__":
    initialize_environment()