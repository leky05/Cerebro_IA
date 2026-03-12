import pandas as pd
from pathlib import Path
import sys

# Importamos las rutas dinámicas desde nuestro config.py
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import ROOT_DIR

class DukascopyProcessor:
    """
    Procesador estandarizado para limpiar y estructurar datos de ticks/velas 
    provenientes de Dukascopy, preparándolos para la base de datos y ML.
    """
    
    def __init__(self):
        # Usamos pathlib para asegurar que las rutas funcionen en cualquier PC
        self.raw_data_dir = ROOT_DIR / "data_ingestion" / "raw"
        self.processed_data_dir = ROOT_DIR / "data_ingestion" / "processed"
        
        # Creamos las subcarpetas si no existen
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

    def process_m1_csv(self, filename: str) -> Path:
        """
        Lee un CSV de velas M1 de Dukascopy, lo limpia, ajusta la zona horaria
        y lo guarda en formato Parquet.
        """
        file_path = self.raw_data_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"❌ No se encontró el archivo: {file_path}")
            
        print(f"🔄 Procesando {filename}...")
        
        # 1. Lectura del CSV
        # Dukascopy suele usar 'Local time' o 'Gmt time' como columna de tiempo
        df = pd.read_csv(file_path)
        
        # 2. Estandarización de columnas a minúsculas para coincidir con la Base de Datos
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        
        # Renombramos la columna de tiempo si es necesario para mantener estándar
        if 'local_time' in df.columns:
            df.rename(columns={'local_time': 'time'}, inplace=True)
        elif 'gmt_time' in df.columns:
            df.rename(columns={'gmt_time': 'time'}, inplace=True)

        # 3. Tratamiento Temporal (Crítico)
        # Convertimos el string a objeto datetime y forzamos la zona horaria UTC
        df['time'] = pd.to_datetime(df['time'], format='mixed')
        if df['time'].dt.tz is None:
            df['time'] = df['time'].dt.tz_localize('UTC')
        else:
            df['time'] = df['time'].dt.tz_convert('UTC')
            
        # Ordenamos cronológicamente y eliminamos duplicados si los hay
        df = df.sort_values('time').drop_duplicates(subset=['time'])
        df = df.set_index('time')
        
        # 4. Guardado en formato Parquet
        output_filename = filename.replace('.csv', '.parquet')
        output_path = self.processed_data_dir / output_filename
        
        # engine='pyarrow' requiere la librería pyarrow (la instalaremos luego si no la tienes)
        df.to_parquet(output_path, engine='pyarrow')
        
        print(f"✅ Archivo procesado y guardado en: {output_path}")
        print(df.head())
        
        return output_path

if __name__ == "__main__":
    # Este bloque solo se ejecuta si corres este script directamente
    processor = DukascopyProcessor()
    print("Módulo de procesamiento inicializado correctamente.")
    
    # ¡Esta es la línea que hace la magia! Sin el '#' al principio.
    processor.process_m1_csv("test_xauusd.csv")