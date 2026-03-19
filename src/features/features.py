import pandas as pd
import numpy as np

class SMCFeatureEngineer:
    """
    Motor de Características enfocado en Smart Money Concepts (SMC).
    Traduce el precio crudo a conceptos de Liquidez, FVG, Estructura y Tiempo.
    """
    
    @staticmethod
    def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
        print("👁️ Activando visión institucional SMC...")
        df_feat = df.copy()
        
        # 1. EL RELOJ (Filtro de Sesiones - Usando UTC como base)
        # Asumimos que la data cruda está en UTC. 
        # NY (10 a 13h Arg) equivale aprox a 13:00-16:00 UTC
        # Londres equivale aprox a 07:00-10:00 UTC
        # Asia equivale aprox a 00:00-03:00 UTC
        df_feat['hour_utc'] = df_feat.index.hour
        df_feat['is_ny_session'] = np.where((df_feat['hour_utc'] >= 13) & (df_feat['hour_utc'] < 16), 1, 0)
        df_feat['is_london_session'] = np.where((df_feat['hour_utc'] >= 7) & (df_feat['hour_utc'] < 10), 1, 0)
        df_feat['is_asian_session'] = np.where((df_feat['hour_utc'] >= 0) & (df_feat['hour_utc'] < 3), 1, 0)
        
        # 2. MICROESTRUCTURA DE LA VELA (Gatillos de Rechazo e Inyección)
        df_feat['body_size'] = abs(df_feat['close'] - df_feat['open'])
        df_feat['total_range'] = df_feat['high'] - df_feat['low']
        df_feat['upper_wick'] = df_feat['high'] - df_feat[['open', 'close']].max(axis=1)
        df_feat['lower_wick'] = df_feat[['open', 'close']].min(axis=1) - df_feat['low']
        
        # Porcentaje de mechas (Define qué tan fuerte es el "Martillo")
        # Sumamos 1e-9 para evitar errores de división por cero en velas planas
        df_feat['lower_wick_pct'] = df_feat['lower_wick'] / (df_feat['total_range'] + 1e-9)
        df_feat['upper_wick_pct'] = df_feat['upper_wick'] / (df_feat['total_range'] + 1e-9)
        
        # 3. VOLUMEN RELATIVO (Confirmación Institucional)
        # Ya corregido el leakage con el shift(1)
        df_feat['vol_sma_10'] = df_feat['volume'].shift(1).rolling(window=10).mean()
        # Ratio: > 1.5 significa que hay un 50% más volumen que la media reciente
        df_feat['vol_relative'] = df_feat['volume'] / (df_feat['vol_sma_10'] + 1e-9)
        
        # 4. INEFICIENCIAS (Fair Value Gaps - FVG)
        # FVG Alcista: El Low actual es mayor al High de hace 2 velas
        df_feat['fvg_bullish'] = np.where(df_feat['low'] > df_feat['high'].shift(2), 1, 0)
        
        # FVG Bajista: El High actual es menor al Low de hace 2 velas
        df_feat['fvg_bearish'] = np.where(df_feat['high'] < df_feat['low'].shift(2), 1, 0)
        
        # 5. PUNTOS LÍQUIDOS - PL (Swing Highs / Lows sin repintado)
        # Un pico se confirma matemáticamente 2 velas DESPUÉS para evitar mirar al futuro
        df_feat['is_swing_high'] = np.where(
            (df_feat['high'].shift(2) > df_feat['high'].shift(1)) & 
            (df_feat['high'].shift(2) > df_feat['high'].shift(3)) & 
            (df_feat['high'].shift(2) > df_feat['high'].shift(4)) & 
            (df_feat['high'].shift(2) > df_feat['high']), 1, 0
        )
        # Registramos el precio exacto de ese Punto Líquido
        df_feat['pl_high_price'] = np.where(df_feat['is_swing_high'] == 1, df_feat['high'].shift(2), np.nan)
        
        df_feat['is_swing_low'] = np.where(
            (df_feat['low'].shift(2) < df_feat['low'].shift(1)) & 
            (df_feat['low'].shift(2) < df_feat['low'].shift(3)) & 
            (df_feat['low'].shift(2) < df_feat['low'].shift(4)) & 
            (df_feat['low'].shift(2) < df_feat['low']), 1, 0
        )
        df_feat['pl_low_price'] = np.where(df_feat['is_swing_low'] == 1, df_feat['low'].shift(2), np.nan)

        # Extendemos el precio del último PL conocido hacia adelante para poder compararlo
        df_feat['last_pl_high'] = df_feat['pl_high_price'].ffill()
        df_feat['last_pl_low'] = df_feat['pl_low_price'].ffill()

        # 6. TOMA DE LIQUIDEZ (Sweeps)
        # Sweep Alcista: El precio baja más que el último Swing Low pero cierra por encima
        df_feat['sweep_bullish'] = np.where(
            (df_feat['low'] < df_feat['last_pl_low']) & (df_feat['close'] > df_feat['last_pl_low']), 1, 0
        )
        
        # Sweep Bajista: El precio sube más que el último Swing High pero cierra por debajo
        df_feat['sweep_bearish'] = np.where(
            (df_feat['high'] > df_feat['last_pl_high']) & (df_feat['close'] < df_feat['last_pl_high']), 1, 0
        )

        # 7. MEMORIA DEL SABUESO (Filtro numérico para el LLM - Punto 12 de Claude)
        # Marcamos si hubo un sweep en las últimas 36 velas (Aprox 3 horas en M5)
        max_velas_sweep = 36
        df_feat['recent_sweep_bullish'] = df_feat['sweep_bullish'].rolling(window=max_velas_sweep, min_periods=1).max()
        df_feat['recent_sweep_bearish'] = df_feat['sweep_bearish'].rolling(window=max_velas_sweep, min_periods=1).max()
        
        # Limpieza de columnas temporales de cálculo
        columnas_a_borrar = ['hour_utc', 'vol_sma_10', 'last_pl_high', 'last_pl_low']
        df_feat.drop(columns=[col for col in columnas_a_borrar if col in df_feat.columns], inplace=True)
        df_feat.dropna(subset=['vol_relative'], inplace=True)
        
        print(f"✅ Ojos SMC listos. Velas procesadas: {len(df_feat)}")
        return df_feat

if __name__ == "__main__":
    # --- PRUEBA DE DIAGNÓSTICO ---
    print("🛠️ Probando el Escáner SMC...")
    # Simulamos datos en horario de Nueva York
    fechas = pd.date_range('2024-01-01 13:00:00', periods=50, freq='5min', tz='UTC')
    np.random.seed(42)
    
    datos_prueba = pd.DataFrame({
        'open': np.random.uniform(2000, 2010, 50),
        'high': np.random.uniform(2010, 2020, 50),
        'low': np.random.uniform(1990, 2000, 50),
        'close': np.random.uniform(2000, 2010, 50),
        'volume': np.random.randint(100, 1000, 50)
    }, index=fechas)
    
    datos_con_features = SMCFeatureEngineer.calculate_features(datos_prueba)
    
    print("\n📊 MUESTRA DE VARIABLES SMC (Última vela):")
    print(datos_con_features.tail(1).T)