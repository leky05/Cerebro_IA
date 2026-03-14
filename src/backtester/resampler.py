import pandas as pd

class DataResampler:
    """
    Módulo institucional para convertir datos de resolución base (M1) 
    a temporalidades superiores (M5, M15, H1, etc.) sobre la marcha.
    """
    
    @staticmethod
    def resample_data(df_m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Convierte un DataFrame de M1 al timeframe deseado.
        
        :param df_m1: DataFrame original en 1 minuto indexado por fecha.
        :param timeframe: String de Pandas (ej: '5min', '15min', '1H', '1D').
        :return: DataFrame agrupado y limpio.
        """
        print(f"⏳ Comprimiendo el tiempo: Convirtiendo M1 a {timeframe}...")
        
        # Diccionario universal de reglas de agrupación para velas japonesas
        aggregation_dict = {
            'open': 'first',   # El precio de apertura es el primero del bloque
            'high': 'max',     # El alto es el máximo del bloque
            'low': 'min',      # El bajo es el mínimo del bloque
            'close': 'last',   # El precio de cierre es el último del bloque
            'volume': 'sum'    # El volumen total se suma
        }
        
        # Ejecutar la compresión matemática
        df_resampled = df_m1.resample(timeframe).agg(aggregation_dict)
        
        # Eliminar las velas vacías (ej: fines de semana donde no hay mercado)
        df_resampled = df_resampled.dropna()
        
        print(f"✅ Compresión terminada. Velas resultantes: {len(df_resampled)}")
        return df_resampled

if __name__ == "__main__":
    # --- PRUEBA DE DIAGNÓSTICO ---
    print("🛠️ Probando el motor de Resampling...")
    
    # Creamos 5 velas de 1 minuto falsas
    fechas = pd.date_range('2024-01-01 10:00:00', periods=5, freq='min')
    datos_prueba = pd.DataFrame({
        'open': [10, 12, 11, 15, 14],
        'high': [12, 13, 15, 16, 18],
        'low': [9, 10, 10, 14, 13],
        'close': [11, 11, 14, 15, 17],
        'volume': [100, 200, 150, 300, 250]
    }, index=fechas)
    
    print("\n📊 VELAS ORIGINALES (M1):")
    print(datos_prueba)
    
    # Comprimimos las 5 velas de 1 minuto en 1 sola vela de 5 minutos
    vela_m5 = DataResampler.resample_data(datos_prueba, '5min')
    
    print("\n📦 VELA COMPRIMIDA (M5):")
    print(vela_m5)