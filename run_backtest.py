import os
import time
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from src.brain import CerebroIA

# Importamos tus Ojos Cuantitativos
try:
    from src.features.features import SMCFeatureEngineer 
    TIENE_FEATURES = True
except ImportError:
    print("⚠️ No se encontró la ruta exacta a features.py. Usando motor SMC de emergencia.")
    TIENE_FEATURES = False

load_dotenv()

def extraer_datos_reales():
    """Conecta a PostgreSQL y extrae Enero 2024 de XAUUSD"""
    print("📥 Conectando a la Bóveda de Datos (PostgreSQL)...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("No se encontró DATABASE_URL en el archivo .env")
    
    engine = create_engine(db_url)
    
    query = """
        SELECT time, open, high, low, close, volume 
        FROM xauusd_m1 
        WHERE time >= '2024-01-01' AND time < '2024-02-01'
        ORDER BY time ASC
    """
    df = pd.read_sql(query, engine)
    df.set_index('time', inplace=True)
    
    print("⏳ Comprimiendo el tiempo a M5...")
    df_m5 = df.resample('5min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    
    return df_m5

def calcular_parametros_trade(direccion, precio_entrada, contexto_velas, buffer_costos=0.25):
    """Calcula Stop Loss estructural y Take Profit 1:2 simulando costos de Vantage"""
    if direccion == "long":
        minimo_sweep = min(vela['low'] for vela in contexto_velas)
        stop_loss = minimo_sweep - buffer_costos
        riesgo = precio_entrada - stop_loss
        take_profit = precio_entrada + (riesgo * 2)
    elif direccion == "short":
        maximo_sweep = max(vela['high'] for vela in contexto_velas)
        stop_loss = maximo_sweep + buffer_costos
        riesgo = stop_loss - precio_entrada
        take_profit = precio_entrada - (riesgo * 2)
        
    return round(stop_loss, 2), round(take_profit, 2), round(riesgo, 2)

def run_real_hybrid_backtest():
    print("🚀 Iniciando Backtest Híbrido REAL (XAUUSD - Enero 2024)...")
    
    try:
        df = extraer_datos_reales()
    except Exception as e:
        print(f"❌ Error al conectar con la base de datos: {e}")
        return
        
    print("👁️ Activando visión institucional SMC...")
    if TIENE_FEATURES:
        df = SMCFeatureEngineer.calculate_features(df)
    
    try:
        ia = CerebroIA()
    except Exception as e:
        print(f"❌ Error al iniciar Cerebro_IA: {e}")
        return

    active_bullish_fvgs = []
    active_bearish_fvgs = []
    trades_activos = []
    historial_trades = []
    
    analisis_realizados = 0
    limite_analisis = 50 # Aumentado para correr el mes completo

    print(f"\n⚙️ Iniciando cacería en el mercado real (Sesión NY: 10 a 13hs Arg)...")

    for i in range(30, len(df)): 
        vela_actual = df.iloc[i]
        fecha_actual = df.index[i]

        # === 1. GESTOR DE POSICIONES (Trade Management) ===
        for trade in trades_activos[:]:
            if trade['direccion'] == 'long':
                if vela_actual['low'] <= trade['sl']:
                    print(f"🔴 [{fecha_actual}] LONG SL Tocado. Salida: {trade['sl']}")
                    trade['resultado'] = 'SL'
                    historial_trades.append(trade)
                    trades_activos.remove(trade)
                elif vela_actual['high'] >= trade['tp']:
                    print(f"🟢 [{fecha_actual}] LONG TP Tocado! Salida: {trade['tp']}")
                    trade['resultado'] = 'TP'
                    historial_trades.append(trade)
                    trades_activos.remove(trade)
            elif trade['direccion'] == 'short':
                if vela_actual['high'] >= trade['sl']:
                    print(f"🔴 [{fecha_actual}] SHORT SL Tocado. Salida: {trade['sl']}")
                    trade['resultado'] = 'SL'
                    historial_trades.append(trade)
                    trades_activos.remove(trade)
                elif vela_actual['low'] <= trade['tp']:
                    print(f"🟢 [{fecha_actual}] SHORT TP Tocado! Salida: {trade['tp']}")
                    trade['resultado'] = 'TP'
                    historial_trades.append(trade)
                    trades_activos.remove(trade)

        # === 2. RADAR ESPACIAL ===
        if df['fvg_bullish'].iloc[i] == 1:
            active_bullish_fvgs.append({'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2], 'creacion': fecha_actual})
            
        if df.get('fvg_bearish', pd.Series(0)).iloc[i] == 1:
            active_bearish_fvgs.append({'top': df['low'].iloc[i-2], 'bottom': df['high'].iloc[i], 'creacion': fecha_actual})
            
        # === 3. MITIGACIÓN Y LLAMADA A IA ===
        # Solo buscamos entradas en la ventana horaria y si no excedimos la cuota
        if (df.index[i].hour >= 13 and df.index[i].hour < 16) and analisis_realizados < limite_analisis:
            
            trade_tomado_esta_vela = False 
            
            # --- COMPRAS ---
            for fvg in active_bullish_fvgs[:]: 
                if df['low'].iloc[i] <= fvg['top']: 
                    if df.get('recent_sweep_bullish', pd.Series(0)).iloc[i] == 1 and not trade_tomado_esta_vela:
                        nuevo_trade = ejecutar_analisis_ia(ia, df, i, fvg, "long", "Alcista")
                        analisis_realizados += 1
                        trade_tomado_esta_vela = True
                        if nuevo_trade:
                            trades_activos.append(nuevo_trade)
                    active_bullish_fvgs.remove(fvg)

            # --- VENTAS ---
            for fvg in active_bearish_fvgs[:]:
                if df['high'].iloc[i] >= fvg['bottom']: 
                    if df.get('recent_sweep_bearish', pd.Series(0)).iloc[i] == 1 and not trade_tomado_esta_vela:
                        nuevo_trade = ejecutar_analisis_ia(ia, df, i, fvg, "short", "Bajista")
                        analisis_realizados += 1
                        trade_tomado_esta_vela = True
                        if nuevo_trade:
                            trades_activos.append(nuevo_trade)
                    active_bearish_fvgs.remove(fvg)

    print("\n🏁 BACKTEST FINALIZADO 🏁")
    print(f"Operaciones totales: {len(historial_trades)}")
    tps = sum(1 for t in historial_trades if t['resultado'] == 'TP')
    sls = sum(1 for t in historial_trades if t['resultado'] == 'SL')
    print(f"✅ Take Profits (1:2): {tps} | ❌ Stop Loss: {sls}")
    if len(historial_trades) > 0:
        print(f"Win Rate Final: {round((tps/len(historial_trades))*100, 2)}%")

def ejecutar_analisis_ia(ia, df, i, fvg, direccion, etiqueta_tipo):
    """Llamada al CerebroIA con reintentos automáticos"""
    print(f"\n==================================================")
    print(f"🐺 [SABUESO] Setup {etiqueta_tipo} detectado en: {df.index[i]}")
    
    precio_entrada = fvg['top'] if direccion == "long" else fvg['bottom']
    bloque_velas = df.iloc[i-29:i+1]
    velas_json = [{"vela": j-29, "open": round(r['open'], 2), "high": round(r['high'], 2), "low": round(r['low'], 2), "close": round(r['close'], 2)} 
                  for j, (idx, r) in enumerate(bloque_velas.iterrows())]
    
    decision = ia.analizar_setup({"trade_direction": direccion, "techo_fvg": round(fvg['top'], 2), "base_fvg": round(fvg['bottom'], 2)}, velas_json)
    
    if decision.get('signal') == 1:
        sl, tp, riesgo = calcular_parametros_trade(direccion, precio_entrada, velas_json)
        print(f"🎯 IA APROBÓ EL TRADE! (Confianza: {decision.get('confidence', 'N/A')})")
        return {"fecha_entrada": df.index[i], "direccion": direccion, "precio_entrada": precio_entrada, "sl": sl, "tp": tp, "riesgo": riesgo, "resultado": None}
    
    print(f"🛑 IA RECHAZÓ EL TRADE. Motivo: {decision.get('invalidation_reason', 'N/A')}")
    return None

if __name__ == "__main__":
    run_real_hybrid_backtest()