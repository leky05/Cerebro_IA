import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Importar nuestros módulos institucionales de la carpeta src
from src.backtester.engine import VectorialBacktester
from src.backtester.resampler import DataResampler

load_dotenv()

def run_crash_test():
    print("🚀 Iniciando Secuencia de Backtest Principal (Crash Test Dummy)...")
    
    # 1. Conectar al Tanque de Datos
    db_url = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    # Extraer 3 meses de prueba (Ej: Enero a Marzo 2024) para que sea ultra rápido
    print("📥 Extrayendo datos reales de XAUUSD (Q1 2024) desde TimescaleDB...")
    query = """
        SELECT time, open, high, low, close, volume 
        FROM xauusd_m1 
        WHERE time >= '2024-01-01' AND time < '2024-04-01'
        ORDER BY time ASC
    """
    # Cargamos los datos crudos
    df_raw = pd.read_sql(query, engine, index_col='time')
    print(f"✅ Se extrajeron {len(df_raw)} velas de M1.")
    
    # 2. Máquina de Tiempo: Convertimos M1 a M15 (15 minutos)
    df_m15 = DataResampler.resample_data(df_raw, '15min')
    
    # 3. El Piloto Automático "Dummy" (Cruce de Medias Móviles - SMA)
    print("🧠 Calculando Estrategia: SMA Crossover (10 vs 50)...")
    df_m15['SMA_Fast'] = df_m15['close'].rolling(window=10).mean()
    df_m15['SMA_Slow'] = df_m15['close'].rolling(window=50).mean()
    
    # Lógica de Trading: 1 (Compra) si la Rápida cruza arriba de la Lenta, sino -1 (Venta)
    df_m15['Signal'] = np.where(df_m15['SMA_Fast'] > df_m15['SMA_Slow'], 1, -1)
    
    # 4. Inyectar al Motor Vectorial (Evaluación con Spread Real)
    backtester = VectorialBacktester(initial_capital=10000.0, spread_pips=1.5)
    resultados = backtester.run_strategy(df_m15, df_m15['Signal'])
    
    # 5. Reporte de Rendimiento
    capital_final = resultados['Equity_Curve'].iloc[-1]
    retorno = ((capital_final - 10000.0) / 10000.0) * 100
    
    print("\n" + "="*40)
    print("📊 REPORTE FINAL DEL CRASH TEST")
    print("="*40)
    print(f"Activo: XAUUSD")
    print(f"Temporalidad Operada: M15")
    print(f"Capital Inicial: $10,000.00")
    print(f"Capital Final: ${capital_final:.2f}")
    print(f"Retorno Neto: {retorno:.2f}%")
    print("="*40)

if __name__ == "__main__":
    run_crash_test()