import pandas as pd
import numpy as np

class VectorialBacktester:
    """
    Motor de simulación de alta velocidad para Cerebro_IA.
    Evalúa estrategias matemáticas sobre datos históricos sin arriesgar capital real.
    """
    
    def __init__(self, initial_capital: float = 10000.0, spread_pips: float = 1.5):
        # Capital inicial de la cuenta de prueba (ej: $10,000)
        self.initial_capital = initial_capital
        
        # El spread promedio de Vantage para el XAUUSD (costo operativo)
        self.spread = spread_pips
        
        # Aquí guardaremos el historial de operaciones simuladas
        self.trades_history = []
        
    def run_strategy(self, data: pd.DataFrame, signals: pd.Series) -> pd.DataFrame:
        """
        Ejecuta la simulación completa vectorizada.
        """
        print(f"Iniciando simulación sobre {len(data)} velas...")
        
        df = data.copy()
        df['Signal'] = signals
        
        # 1. Rendimiento del Mercado (Cuánto subió o bajó el precio entre velas)
        df['Market_Returns'] = df['close'].pct_change()
        
        # 2. Rendimiento de la Estrategia (Desplazamos la señal 1 vela al futuro)
        # Si ayer dije "1" (Compra), hoy gano el Market_Return de hoy.
        df['Strategy_Returns'] = df['Market_Returns'] * df['Signal'].shift(1)
        
        # 3. Calcular los cambios de posición para cobrar el Spread
        # diff() detecta cuando cambiamos de 0 a 1 (1 trade) o de 1 a -1 (2 trades: cerrar y abrir)
        df['Trades'] = df['Signal'].diff().abs().fillna(0)
        
        # En XAUUSD, 1 pip estándar es 0.1 en el precio. Calculamos el costo porcentual.
        pip_value = 0.1 
        costo_absoluto = self.spread * pip_value
        df['Spread_Cost_Pct'] = (costo_absoluto / df['close']) * df['Trades']
        
        # 4. Descontamos las comisiones del broker a nuestras ganancias/pérdidas
        df['Strategy_Returns'] -= df['Spread_Cost_Pct']
        
        # 5. La Curva de Capital (Equity Curve): Interés compuesto de la cuenta
        df['Equity_Curve'] = self.initial_capital * (1 + df['Strategy_Returns']).cumprod()
        
        # Limpiamos el primer valor vacío
        df = df.dropna()
        
        print("✅ Simulación terminada.")
        return df

if __name__ == "__main__":
    # --- PRUEBA DE FUEGO DEL MOTOR ---
    # Vamos a inventar unos datos de prueba rápidos para ver si el motor arranca
    print("🛠️ Ejecutando prueba de diagnóstico del Motor...")
    
    # Creamos 5 velas falsas de XAUUSD
    fechas = pd.date_range('2024-01-01', periods=5, freq='min')
    datos_prueba = pd.DataFrame({
        'close': [2000.0, 2002.0, 1998.0, 2005.0, 2010.0]
    }, index=fechas)
    
    # Inventamos señales: 1 (Compra), 1 (Mantiene), -1 (Vende), 1 (Compra), 0 (Cierra)
    señales_prueba = pd.Series([1, 1, -1, 1, 0], index=fechas)
    
    # Encendemos el simulador con $10,000
    motor = VectorialBacktester(initial_capital=10000.0, spread_pips=1.5)
    resultado = motor.run_strategy(datos_prueba, señales_prueba)
    
    print("\n📊 RESULTADO DEL SIMULADOR (Prueba):")
    print(resultado[['close', 'Signal', 'Strategy_Returns', 'Equity_Curve']])