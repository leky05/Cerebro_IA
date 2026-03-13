import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Cargar secretos desde el archivo .env
load_dotenv()

class DatabaseManager:
    def __init__(self):
        # Lee la URL de conexión de tu bóveda local
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("CRÍTICO: No se encontró DATABASE_URL en el archivo .env")

    def insert_m1_data(self, parquet_path: str):
        print(f"🔌 Conectando a TimescaleDB...")
        
        # 1. Leer el archivo Parquet procesado
        try:
            df = pd.read_parquet(parquet_path)
            # Como 'time' quedó como índice al procesarlo, lo convertimos a columna
            if df.index.name == 'time':
                df = df.reset_index()
        except Exception as e:
            print(f"❌ Error al leer el archivo Parquet: {e}")
            return
        
        # 2. Conectar a PostgreSQL
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # 3. Preparar los datos como una lista de tuplas para inserción ultrarrápida
            records = df[['time', 'open', 'high', 'low', 'close', 'volume']].values.tolist()
            
            # La consulta SQL con ON CONFLICT para evitar duplicados si corres el script 2 veces
            insert_query = """
                INSERT INTO xauusd_m1 (time, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (time) DO NOTHING;
            """
            
            print(f"🚀 Inyectando {len(records)} velas de {parquet_path}...")
            execute_values(cursor, insert_query, records)
            
            # Confirmar los cambios y cerrar la conexión
            conn.commit()
            cursor.close()
            conn.close()
            print("✅ Inyección completada exitosamente. Los datos ya están en el motor.")
            
        except Exception as e:
            print(f"❌ Error crítico en la base de datos: {e}")

if __name__ == "__main__":
    db = DatabaseManager()
    
    # Inyectamos el año 2024 completo al tanque
    db.insert_m1_data("data_ingestion/processed/xauusd_2024.parquet")