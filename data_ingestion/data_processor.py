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

        print(f"🔄 Procesando {filename}...")
        
        file_path = self.raw_data_dir / filename
        df = pd.read_csv(file_path)
        
        # 1. Estandarizar nombre de columna (Dukascopy usa 'timestamp')
        if 'timestamp' in df.columns:
            df.rename(columns={'timestamp': 'time'}, inplace=True)
            
        # 2. Agregar volumen en 0.0 si Dukascopy no lo incluyó (la Base de Datos lo exige)
        if 'volume' not in df.columns:
            df['volume'] = 0.0
            
        # 3. Convertir a formato de Tiempo (Soporta Milisegundos o Texto)
        try:
            # Intenta leerlo como milisegundos (formato masivo de Dukascopy)
            df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
        except ValueError:
            # Si falla, intenta leerlo como texto normal (nuestro archivo de prueba)
            df['time'] = pd.to_datetime(df['time'], format='mixed', utc=True)
            
        # 4. Ordenar y establecer el índice
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        df = df.set_index('time')
        
        # 5. Guardado en formato Parquet
        output_filename = filename.replace('.csv', '.parquet')
        output_path = self.processed_data_dir / output_filename
        
        df.to_parquet(output_path, engine='pyarrow')
        
        print(f"✅ Archivo procesado y guardado en: {output_path}")
        print(df.head())
        
        return output_path

if __name__ == "__main__":
    import os
    processor = DukascopyProcessor()
    print("Iniciando refinería masiva histórica...")
    
    # Busca todos los CSV en raw, pero excluye el de 2024 que ya procesamos
    archivos = [f for f in os.listdir(processor.raw_data_dir) if f.endswith('.csv') and '2024' not in f]
    
    for archivo in archivos:
        processor.process_m1_csv(archivo)
        
    print("¡Toda la historia antigua ha sido convertida a .parquet!")