import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Importar nuestros módulos institucionales
from src.backtester.engine import VectorialBacktester
from src.backtester.resampler import DataResampler
from src.features.features import SMCFeatureEngineer
from src.strategy.smc import SMCStateMachine

load_dotenv()

def run_smc_radar_test():
    print("🚀 Iniciando Secuencia de Backtest (V4 - Radar con Memoria)...")
    
    db_url = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(db_url)
    
    print("📥 Extrayendo datos reales de XAUUSD (Q1 2024)...")
    query = """
        SELECT time, open, high, low, close, volume 
        FROM xauusd_m1 
        WHERE time >= '2024-01-01' AND time < '2024-04-01'
        ORDER BY time ASC
    """
    df_raw = pd.read_sql(query, engine, index_col='time')
    
    # 1. Máquina de Tiempo a M5
    df_m5 = DataResampler.resample_data(df_raw, '5min')
    
    # 2. Los Ojos (Escáner SMC)
    df_features = SMCFeatureEngineer.calculate_features(df_m5)
    
    # 3. La Memoria (Máquina de Estados)
    # Filtramos para que solo busque en la sesión de NY
    radar = SMCStateMachine(session_filter='NY')
    df_signals = radar.run(df_features)
    
    # Verificamos si la máquina encontró algo
    total_compras = df_signals['Signal'].sum()
    print(f"\n🎯 RESUMEN DEL RADAR:")
    print(f"Sesión Operada: NY")
    print(f"Gatillos de Compra ejecutados: {int(total_compras)}")
    
    if total_compras > 0:
        # 4. Enviar al Motor Vectorial
        print("\n⚙️ Procesando operaciones en el Motor Vectorial...")
        backtester = VectorialBacktester(initial_capital=10000.0, spread_pips=1.5)
        resultados = backtester.run_strategy(df_signals, df_signals['Signal'])
        
        capital_final = resultados['Equity_Curve'].iloc[-1]
        retorno = ((capital_final - 10000.0) / 10000.0) * 100
        
        print("\n" + "="*40)
        print("📊 REPORTE FINAL DEL CRASH TEST V4")
        print("="*40)
        print(f"Activo: XAUUSD")
        print(f"Temporalidad Operada: M5")
        print(f"Capital Inicial: $10,000.00")
        print(f"Capital Final: ${capital_final:.2f}")
        print(f"Retorno Neto: {retorno:.2f}%")
        print("="*40)
    else:
        print("\n⚠️ No se encontraron Set-Ups perfectos en este trimestre con la rigidez actual.")

if __name__ == "__main__":
    run_smc_radar_test()