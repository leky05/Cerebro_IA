import os
import time
import numpy as np
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

# ── Parámetro de Cooldown post-Sweep (alineado con smc.py) ───
SWEEP_COOLDOWN_VELAS = 8  # ~40 min en M5


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

    # ── Memorias Espaciales Persistentes (alineadas con smc.py v2.1) ──
    active_bullish_fvgs = []     # {'top', 'bottom', 'creacion'}
    active_bearish_fvgs = []     # {'top', 'bottom', 'creacion'}
    active_swing_highs = []      # {'price', 'idx'}
    active_swing_lows = []       # {'price', 'idx'}

    # Cooldowns post-sweep
    sweep_bull_cooldown = 0
    sweep_bear_cooldown = 0

    trades_activos = []
    historial_trades = []
    
    analisis_realizados = 0
    limite_analisis = 50
    cuota_agotada = False  # Flag de parada por cuota diaria

    # ── Extracción a arrays para velocidad en el loop ─────────────
    lows = df['low'].values
    highs = df['high'].values
    closes = df['close'].values
    fvgs_bull = df['fvg_bullish'].values
    fvgs_bear = df['fvg_bearish'].values if 'fvg_bearish' in df.columns else np.zeros(len(df))
    is_sh = df['is_swing_high'].values
    is_sl_arr = df['is_swing_low'].values
    pl_high_prices = df['pl_high_price'].values
    pl_low_prices = df['pl_low_price'].values

    # Contadores de diagnóstico
    sweeps_bull_total = 0
    sweeps_bear_total = 0

    print(f"\n⚙️ Iniciando cacería en el mercado real (Sesión NY: 10 a 13hs Arg)...")

    for i in range(30, len(df)): 
        vela_actual = df.iloc[i]
        fecha_actual = df.index[i]

        # ═══════════════════════════════════════════════════════════
        # 0. CHECK DE CUOTA — Si Gemini Free Tier se agotó, salimos
        # ═══════════════════════════════════════════════════════════
        if cuota_agotada:
            # Seguimos procesando el gestor de posiciones para
            # cerrar trades abiertos, pero no enviamos más a la IA
            for trade in trades_activos[:]:
                if trade['direccion'] == 'long':
                    if vela_actual['low'] <= trade['sl']:
                        trade['resultado'] = 'SL'
                        historial_trades.append(trade)
                        trades_activos.remove(trade)
                    elif vela_actual['high'] >= trade['tp']:
                        trade['resultado'] = 'TP'
                        historial_trades.append(trade)
                        trades_activos.remove(trade)
                elif trade['direccion'] == 'short':
                    if vela_actual['high'] >= trade['sl']:
                        trade['resultado'] = 'SL'
                        historial_trades.append(trade)
                        trades_activos.remove(trade)
                    elif vela_actual['low'] <= trade['tp']:
                        trade['resultado'] = 'TP'
                        historial_trades.append(trade)
                        trades_activos.remove(trade)
            # Si no quedan trades abiertos, ya no hay nada que hacer
            if not trades_activos:
                break
            continue

        # ═══════════════════════════════════════════════════════════
        # 1. GESTOR DE POSICIONES (Trade Management)
        # ═══════════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════════
        # 2. REGISTRO DE ZONAS FVG (Ocurre 24/5)
        # ═══════════════════════════════════════════════════════════
        if fvgs_bull[i] == 1:
            active_bullish_fvgs.append({
                'top': lows[i],
                'bottom': highs[i - 2],
                'creacion': fecha_actual,
            })
            
        if fvgs_bear[i] == 1:
            active_bearish_fvgs.append({
                'top': lows[i - 2],
                'bottom': highs[i],
                'creacion': fecha_actual,
            })

        # ═══════════════════════════════════════════════════════════
        # 3. REGISTRO DE PUNTOS LÍQUIDOS (Memoria Espacial)
        # ═══════════════════════════════════════════════════════════
        if is_sh[i] == 1 and not np.isnan(pl_high_prices[i]):
            active_swing_highs.append({
                'price': pl_high_prices[i],
                'idx': i,
            })

        if is_sl_arr[i] == 1 and not np.isnan(pl_low_prices[i]):
            active_swing_lows.append({
                'price': pl_low_prices[i],
                'idx': i,
            })

        # ═══════════════════════════════════════════════════════════
        # 4. DETECCIÓN DE SWEEPS EN TIEMPO REAL
        # ═══════════════════════════════════════════════════════════
        for pl in active_swing_lows[:]:
            if lows[i] < pl['price']:
                if closes[i] > pl['price']:
                    sweep_bull_cooldown = SWEEP_COOLDOWN_VELAS
                    sweeps_bull_total += 1
                active_swing_lows.remove(pl)

        for pl in active_swing_highs[:]:
            if highs[i] > pl['price']:
                if closes[i] < pl['price']:
                    sweep_bear_cooldown = SWEEP_COOLDOWN_VELAS
                    sweeps_bear_total += 1
                active_swing_highs.remove(pl)

        # ═══════════════════════════════════════════════════════════
        # 5. GARBAGE COLLECTOR DE FVGs
        # ═══════════════════════════════════════════════════════════
        cierre = closes[i]
        active_bullish_fvgs = [
            fvg for fvg in active_bullish_fvgs
            if cierre >= fvg['bottom']
        ]
        active_bearish_fvgs = [
            fvg for fvg in active_bearish_fvgs
            if cierre <= fvg['top']
        ]

        # ═══════════════════════════════════════════════════════════
        # 6. GATILLO — Triple Confluencia + Llamada a IA
        # ═══════════════════════════════════════════════════════════
        if not (df.index[i].hour >= 13 and df.index[i].hour < 16):
            sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
            sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)
            continue

        if analisis_realizados >= limite_analisis:
            sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
            sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)
            continue

        trade_tomado_esta_vela = False 

        # --- COMPRAS (Long) ---
        if sweep_bull_cooldown > 0 and not trade_tomado_esta_vela:
            for fvg in active_bullish_fvgs[:]: 
                if lows[i] <= fvg['top']:
                    decision = ejecutar_analisis_ia(ia, df, i, fvg, "long", "Alcista")
                    analisis_realizados += 1
                    trade_tomado_esta_vela = True

                    # Check de cuota diaria agotada
                    if decision.get('_cuota_agotada'):
                        cuota_agotada = True
                        active_bullish_fvgs.remove(fvg)
                        break

                    if decision:
                        trades_activos.append(decision)
                    active_bullish_fvgs.remove(fvg)
                    break

        # --- VENTAS (Short) ---
        if sweep_bear_cooldown > 0 and not trade_tomado_esta_vela and not cuota_agotada:
            for fvg in active_bearish_fvgs[:]:
                if highs[i] >= fvg['bottom']:
                    decision = ejecutar_analisis_ia(ia, df, i, fvg, "short", "Bajista")
                    analisis_realizados += 1
                    trade_tomado_esta_vela = True

                    # Check de cuota diaria agotada
                    if decision.get('_cuota_agotada'):
                        cuota_agotada = True
                        active_bearish_fvgs.remove(fvg)
                        break

                    if decision:
                        trades_activos.append(decision)
                    active_bearish_fvgs.remove(fvg)
                    break

        # Decremento de cooldowns
        sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
        sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)

    # ═══════════════════════════════════════════════════════════
    # RESUMEN FINAL
    # ═══════════════════════════════════════════════════════════
    print("\n🏁 BACKTEST FINALIZADO 🏁")
    if cuota_agotada:
        print("⚠️  Backtest interrumpido por cuota diaria de Gemini Free Tier (20 req/día).")
    print(f"Análisis IA realizados: {analisis_realizados}")
    print(f"Sweeps detectados -> Alcistas: {sweeps_bull_total} | Bajistas: {sweeps_bear_total}")
    print(f"PLs vivos al cierre: {len(active_swing_highs) + len(active_swing_lows)}")
    print(f"FVGs vivos al cierre: {len(active_bullish_fvgs) + len(active_bearish_fvgs)}")
    print(f"Operaciones totales: {len(historial_trades)}")
    tps = sum(1 for t in historial_trades if t['resultado'] == 'TP')
    sls = sum(1 for t in historial_trades if t['resultado'] == 'SL')
    print(f"✅ Take Profits (1:2): {tps} | ❌ Stop Loss: {sls}")
    if len(historial_trades) > 0:
        print(f"Win Rate Final: {round((tps/len(historial_trades))*100, 2)}%")


def ejecutar_analisis_ia(ia, df, i, fvg, direccion, etiqueta_tipo):
    """
    Llamada al CerebroIA con manejo de cuota.
    Retorna:
      - dict con datos del trade si IA aprobó
      - dict con _cuota_agotada=True si se agotó la cuota
      - None si IA rechazó el trade
    """
    print(f"\n==================================================")
    print(f"🐺 [SABUESO] Setup {etiqueta_tipo} detectado en: {df.index[i]}")
    
    precio_entrada = fvg['top'] if direccion == "long" else fvg['bottom']
    bloque_velas = df.iloc[i-29:i+1]
    velas_json = [{"vela": j-29, "open": round(r['open'], 2), "high": round(r['high'], 2), "low": round(r['low'], 2), "close": round(r['close'], 2)} 
                  for j, (idx, r) in enumerate(bloque_velas.iterrows())]
    
    decision = ia.analizar_setup({"trade_direction": direccion, "techo_fvg": round(fvg['top'], 2), "base_fvg": round(fvg['bottom'], 2)}, velas_json)
    
    # Propagar señal de cuota agotada al backtester
    if decision.get('_cuota_agotada'):
        return decision

    if decision.get('signal') == 1:
        sl, tp, riesgo = calcular_parametros_trade(direccion, precio_entrada, velas_json)
        print(f"🎯 IA APROBÓ EL TRADE! (Confianza: {decision.get('confidence', 'N/A')})")
        return {"fecha_entrada": df.index[i], "direccion": direccion, "precio_entrada": precio_entrada, "sl": sl, "tp": tp, "riesgo": riesgo, "resultado": None}
    
    print(f"🛑 IA RECHAZÓ EL TRADE. Motivo: {decision.get('invalidation_reason', decision.get('reasoning', 'N/A'))}")
    return None


if __name__ == "__main__":
    run_real_hybrid_backtest()