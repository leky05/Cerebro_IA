"""
Cerebro_IA — Diagnóstico Visual en Tiempo Real
================================================
Ejecutá este script cuando quieras auditar exactamente lo que
el bot está "viendo" en este momento.

Descarga las mismas velas que run_forward.py, corre el mismo
SMCFeatureEngineer, y construye la Memoria Espacial paso a paso
mostrándote cada FVG, PL, Sweep y Cooldown activo.

Uso:
    python diagnostico_visual.py
"""

import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from src.features.features import SMCFeatureEngineer

# ── Configuración (idéntica a run_forward.py) ────────────────
SIMBOLO_ORO = "XAUUSD+"
TEMPORALIDAD = mt5.TIMEFRAME_M5
SWEEP_COOLDOWN_VELAS = 16  # ~80 min en M5
FVG_MIN_SIZE = 3.0         # Ignorar FVGs menores a 3 pts (ruido)


def obtener_velas_mt5(cantidad=100):
    """Descarga las mismas velas que usa el bot."""
    if not mt5.initialize():
        print("❌ Error al conectar con MetaTrader 5.")
        return None
    velas = mt5.copy_rates_from_pos(SIMBOLO_ORO, TEMPORALIDAD, 0, cantidad)
    if velas is None:
        print(f"❌ No se pudieron obtener datos de {SIMBOLO_ORO}.")
        return None
    df = pd.DataFrame(velas)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.rename(columns={'tick_volume': 'volume'}, inplace=True)
    df.set_index('time', inplace=True)
    return df


def run_diagnostico():
    print("=" * 60)
    print("🔍 DIAGNÓSTICO VISUAL — Cerebro_IA")
    print("=" * 60)

    # ── 1. Descargar velas ────────────────────────────────────
    df = obtener_velas_mt5()
    if df is None:
        return
    print(f"\n📥 Velas descargadas: {len(df)}")
    print(f"   Rango: {df.index[0]} → {df.index[-1]}")
    print(f"   Última vela CERRADA: {df.index[-2]}")
    print(f"   Vela en FORMACIÓN:   {df.index[-1]}")

    # ── 2. Calcular features ─────────────────────────────────
    df = SMCFeatureEngineer.calculate_features(df)

    # ── 3. Extraer arrays (misma lógica que run_forward.py) ──
    lows = df['low'].values
    highs = df['high'].values
    closes = df['close'].values
    fvgs_bull = df['fvg_bullish'].values
    fvgs_bear = (
        df['fvg_bearish'].values
        if 'fvg_bearish' in df.columns
        else np.zeros(len(df))
    )
    is_sh = df['is_swing_high'].values
    is_sl_arr = df['is_swing_low'].values
    pl_high_prices = df['pl_high_price'].values
    pl_low_prices = df['pl_low_price'].values

    # PLs Menores (lookback corto)
    is_sh_minor = df['is_swing_high_minor'].values
    is_sl_minor = df['is_swing_low_minor'].values
    pl_high_prices_minor = df['pl_high_price_minor'].values
    pl_low_prices_minor = df['pl_low_price_minor'].values

    # ── 4. Construir Memoria Espacial ────────────────────────
    active_bullish_fvgs = []
    active_bearish_fvgs = []
    active_swing_highs = []        # PLs mayores (lookback=10)
    active_swing_lows = []         # PLs mayores (lookback=10)
    active_swing_highs_minor = []  # PLs menores (lookback=5)
    active_swing_lows_minor = []   # PLs menores (lookback=5)
    sweep_cooldown = 0  # Unificado

    # Historial de eventos para el log
    eventos_sweeps = []
    eventos_fvgs_creados = []
    eventos_fvgs_eliminados = []

    indice_fin = len(df) - 1  # Excluir vela en formación

    for i in range(2, indice_fin):
        timestamp = df.index[i]

        # A. Registro de FVGs (filtro mínimo: >= FVG_MIN_SIZE pts)
        if fvgs_bull[i] == 1:
            size = lows[i] - highs[i - 2]
            if size >= FVG_MIN_SIZE:
                fvg = {
                    'top': round(lows[i], 2),
                    'bottom': round(highs[i - 2], 2),
                    'creacion': timestamp,
                }
                active_bullish_fvgs.append(fvg)
                eventos_fvgs_creados.append(
                    f"   🟢 FVG BULL creado en {timestamp} | "
                    f"Zona: {fvg['bottom']} — {fvg['top']} "
                    f"({size:.1f} pts)"
                )

        if fvgs_bear[i] == 1:
            size = lows[i - 2] - highs[i]
            if size >= FVG_MIN_SIZE:
                fvg = {
                    'top': round(lows[i - 2], 2),
                    'bottom': round(highs[i], 2),
                    'creacion': timestamp,
                }
                active_bearish_fvgs.append(fvg)
                eventos_fvgs_creados.append(
                    f"   🔴 FVG BEAR creado en {timestamp} | "
                    f"Zona: {fvg['bottom']} — {fvg['top']} "
                    f"({size:.1f} pts)"
                )

        # B. Registro de PLs (Mayores + Menores)
        if is_sh[i] == 1 and not np.isnan(pl_high_prices[i]):
            active_swing_highs.append({
                'price': pl_high_prices[i],
                'timestamp': timestamp,
                'tipo': 'MAYOR',
            })
        if is_sl_arr[i] == 1 and not np.isnan(pl_low_prices[i]):
            active_swing_lows.append({
                'price': pl_low_prices[i],
                'timestamp': timestamp,
                'tipo': 'MAYOR',
            })
        if is_sh_minor[i] == 1 and not np.isnan(pl_high_prices_minor[i]):
            active_swing_highs_minor.append({
                'price': pl_high_prices_minor[i],
                'timestamp': timestamp,
                'tipo': 'MENOR',
            })
        if is_sl_minor[i] == 1 and not np.isnan(pl_low_prices_minor[i]):
            active_swing_lows_minor.append({
                'price': pl_low_prices_minor[i],
                'timestamp': timestamp,
                'tipo': 'MENOR',
            })

        # C. Eliminación de PLs (cualquier breach activa contexto)
        for pl in active_swing_lows[:]:
            if lows[i] < pl['price']:
                sweep_cooldown = SWEEP_COOLDOWN_VELAS
                eventos_sweeps.append(
                    f"   ⚡ PL ELIMINADO [{pl['tipo']}] SL en {timestamp} | "
                    f"Precio: {round(pl['price'], 2)} "
                    f"(creado {pl['timestamp']})"
                )
                active_swing_lows.remove(pl)

        for pl in active_swing_lows_minor[:]:
            if lows[i] < pl['price']:
                sweep_cooldown = SWEEP_COOLDOWN_VELAS
                eventos_sweeps.append(
                    f"   ⚡ PL ELIMINADO [{pl['tipo']}] SL en {timestamp} | "
                    f"Precio: {round(pl['price'], 2)} "
                    f"(creado {pl['timestamp']})"
                )
                active_swing_lows_minor.remove(pl)

        for pl in active_swing_highs[:]:
            if highs[i] > pl['price']:
                sweep_cooldown = SWEEP_COOLDOWN_VELAS
                eventos_sweeps.append(
                    f"   ⚡ PL ELIMINADO [{pl['tipo']}] SH en {timestamp} | "
                    f"Precio: {round(pl['price'], 2)} "
                    f"(creado {pl['timestamp']})"
                )
                active_swing_highs.remove(pl)

        for pl in active_swing_highs_minor[:]:
            if highs[i] > pl['price']:
                sweep_cooldown = SWEEP_COOLDOWN_VELAS
                eventos_sweeps.append(
                    f"   ⚡ PL ELIMINADO [{pl['tipo']}] SH en {timestamp} | "
                    f"Precio: {round(pl['price'], 2)} "
                    f"(creado {pl['timestamp']})"
                )
                active_swing_highs_minor.remove(pl)

        # D. Garbage Collector de FVGs
        cierre = closes[i]
        antes_bull = len(active_bullish_fvgs)
        antes_bear = len(active_bearish_fvgs)

        active_bullish_fvgs = [
            fvg for fvg in active_bullish_fvgs
            if cierre >= fvg['bottom']
        ]
        active_bearish_fvgs = [
            fvg for fvg in active_bearish_fvgs
            if cierre <= fvg['top']
        ]

        eliminados_bull = antes_bull - len(active_bullish_fvgs)
        eliminados_bear = antes_bear - len(active_bearish_fvgs)
        if eliminados_bull > 0:
            eventos_fvgs_eliminados.append(
                f"   🗑️ {eliminados_bull} FVG BULL invalidado(s) "
                f"en {timestamp} (cierre: {round(cierre, 2)})"
            )
        if eliminados_bear > 0:
            eventos_fvgs_eliminados.append(
                f"   🗑️ {eliminados_bear} FVG BEAR invalidado(s) "
                f"en {timestamp} (cierre: {round(cierre, 2)})"
            )

        # E. Decrementar cooldown
        sweep_cooldown = max(0, sweep_cooldown - 1)

    # ═══════════════════════════════════════════════════════════
    # REPORTE FINAL
    # ═══════════════════════════════════════════════════════════
    ultima_cerrada = df.index[indice_fin - 1]
    precio_actual = closes[indice_fin - 1]

    print(f"\n{'=' * 60}")
    print(f"📊 ESTADO DE LA MEMORIA ESPACIAL")
    print(f"   (al cierre de {ultima_cerrada})")
    print(f"   Precio de cierre: {round(precio_actual, 2)}")
    print(f"{'=' * 60}")

    # ── FVGs Activos ──────────────────────────────────────────
    print(f"\n🟩 FVGs BULLISH ACTIVOS ({len(active_bullish_fvgs)}):")
    if active_bullish_fvgs:
        for fvg in active_bullish_fvgs:
            distancia = round(precio_actual - fvg['top'], 2)
            ancho = round(fvg['top'] - fvg['bottom'], 1)
            en_zona = "👈 PRECIO EN ZONA" if lows[indice_fin - 1] <= fvg['top'] else ""
            print(
                f"   Zona: {fvg['bottom']} — {fvg['top']} ({ancho}pts) | "
                f"Creado: {fvg['creacion']} | "
                f"Dist: {distancia} pts {en_zona}"
            )
    else:
        print("   (ninguno)")

    print(f"\n🟥 FVGs BEARISH ACTIVOS ({len(active_bearish_fvgs)}):")
    if active_bearish_fvgs:
        for fvg in active_bearish_fvgs:
            distancia = round(fvg['bottom'] - precio_actual, 2)
            ancho = round(fvg['top'] - fvg['bottom'], 1)
            en_zona = "👈 PRECIO EN ZONA" if highs[indice_fin - 1] >= fvg['bottom'] else ""
            print(
                f"   Zona: {fvg['bottom']} — {fvg['top']} ({ancho}pts) | "
                f"Creado: {fvg['creacion']} | "
                f"Dist: {distancia} pts {en_zona}"
            )
    else:
        print("   (ninguno)")

    # ── PLs Activos (ambas capas) ────────────────────────────
    todos_sh = (
        [dict(pl, tipo='MAYOR') if 'tipo' not in pl else pl
         for pl in active_swing_highs]
        + [dict(pl, tipo='MENOR') if 'tipo' not in pl else pl
           for pl in active_swing_highs_minor]
    )
    todos_sl = (
        [dict(pl, tipo='MAYOR') if 'tipo' not in pl else pl
         for pl in active_swing_lows]
        + [dict(pl, tipo='MENOR') if 'tipo' not in pl else pl
           for pl in active_swing_lows_minor]
    )

    print(f"\n📍 SWING HIGHS ACTIVOS ({len(todos_sh)}):")
    if todos_sh:
        for pl in sorted(todos_sh, key=lambda x: x['price'], reverse=True):
            etiqueta = "🔵" if pl['tipo'] == 'MAYOR' else "⚪"
            print(
                f"   {etiqueta} [{pl['tipo']}] "
                f"Precio: {round(pl['price'], 2)} | "
                f"Detectado: {pl['timestamp']}"
            )
    else:
        print("   (ninguno)")

    print(f"\n📍 SWING LOWS ACTIVOS ({len(todos_sl)}):")
    if todos_sl:
        for pl in sorted(todos_sl, key=lambda x: x['price']):
            etiqueta = "🔵" if pl['tipo'] == 'MAYOR' else "⚪"
            print(
                f"   {etiqueta} [{pl['tipo']}] "
                f"Precio: {round(pl['price'], 2)} | "
                f"Detectado: {pl['timestamp']}"
            )
    else:
        print("   (ninguno)")

    # ── Cooldown ──────────────────────────────────────────────
    print(f"\n⏱️ COOLDOWN:")
    print(
        f"   Contexto PL: {sweep_cooldown} velas restantes "
        f"({'🟢 ACTIVO' if sweep_cooldown > 0 else '⚪ inactivo'})"
    )

    # ── Evaluación de Gatillo ─────────────────────────────────
    print(f"\n{'=' * 60}")
    print("🎯 EVALUACIÓN DE GATILLO (última vela cerrada):")
    print(f"{'=' * 60}")

    gatillo_posible = False

    if sweep_cooldown > 0:
        for fvg in active_bullish_fvgs:
            if lows[indice_fin - 1] <= fvg['top']:
                print(
                    f"   ✅ LONG POSIBLE: PL eliminado + "
                    f"precio mitigando FVG Bullish "
                    f"({fvg['bottom']} — {fvg['top']})"
                )
                gatillo_posible = True
                break

        for fvg in active_bearish_fvgs:
            if highs[indice_fin - 1] >= fvg['bottom']:
                print(
                    f"   ✅ SHORT POSIBLE: PL eliminado + "
                    f"precio mitigando FVG Bearish "
                    f"({fvg['bottom']} — {fvg['top']})"
                )
                gatillo_posible = True
                break

    if not gatillo_posible:
        razones = []
        if sweep_cooldown == 0:
            razones.append("No hay PLs eliminados recientemente (cooldown = 0)")
        else:
            en_bull = any(
                lows[indice_fin - 1] <= fvg['top']
                for fvg in active_bullish_fvgs
            )
            en_bear = any(
                highs[indice_fin - 1] >= fvg['bottom']
                for fvg in active_bearish_fvgs
            )
            if not en_bull and not en_bear:
                razones.append(
                    "Cooldown activo pero precio NO está "
                    "mitigando ningún FVG"
                )
        if not active_bullish_fvgs and not active_bearish_fvgs:
            razones.append("No hay FVGs activos en memoria")

        print("   ❌ NO HAY GATILLO. Razón(es):")
        for r in razones:
            print(f"      → {r}")

    # ── Historial de Eventos Recientes ────────────────────────
    print(f"\n{'=' * 60}")
    print("📜 ÚLTIMOS EVENTOS DETECTADOS:")
    print(f"{'=' * 60}")

    print(f"\n   Sweeps ({len(eventos_sweeps)} total):")
    for ev in eventos_sweeps[-5:]:
        print(ev)
    if not eventos_sweeps:
        print("   (ninguno en las últimas 100 velas)")

    print(f"\n   FVGs Creados ({len(eventos_fvgs_creados)} total):")
    for ev in eventos_fvgs_creados[-5:]:
        print(ev)

    print(f"\n   FVGs Eliminados ({len(eventos_fvgs_eliminados)} total):")
    for ev in eventos_fvgs_eliminados[-5:]:
        print(ev)

    # ── Últimas 5 velas (para comparar con TradingView) ──────
    print(f"\n{'=' * 60}")
    print("🕯️ ÚLTIMAS 5 VELAS CERRADAS (para comparar con TradingView):")
    print(f"{'=' * 60}")
    ultimas = df.iloc[-6:-1]  # 5 velas cerradas (excluye la en formación)
    for idx, row in ultimas.iterrows():
        direccion = "🟢" if row['close'] >= row['open'] else "🔴"
        print(
            f"   {direccion} {idx} | "
            f"O:{round(row['open'], 2)} "
            f"H:{round(row['high'], 2)} "
            f"L:{round(row['low'], 2)} "
            f"C:{round(row['close'], 2)} "
            f"V:{int(row['volume'])}"
        )

    print(f"\n{'=' * 60}")
    print("✅ Diagnóstico completo.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_diagnostico()
