import pandas as pd
import numpy as np


class SMCStateMachine:
    """
    Máquina de Estados Institucional v2.1 — Cerebro_IA
    ====================================================
    Memoria Espacial Completa: FVGs + Puntos Líquidos.

    Arquitectura de memoria persistente:
      ┌──────────────────────────────────────────────────────┐
      │  active_bullish_fvgs   — Zonas de demanda (FVG)     │
      │  active_bearish_fvgs   — Zonas de oferta (FVG)      │
      │  active_swing_highs    — Piscinas de liquidez arriba │
      │  active_swing_lows     — Piscinas de liquidez abajo  │
      └──────────────────────────────────────────────────────┘
      Todas las zonas viven hasta que el precio las mitigue.
      NO hay ventanas de tiempo (rolling). La liquidez
      estructural no vence: vence cuando es barrida.

    Flujo por vela:
      1. REGISTRO     — FVGs y PLs nuevos entran a memoria.
      2. SWEEP CHECK  — ¿El precio barrió algún PL activo?
                        Si sí → eliminar PL + activar cooldown.
      3. GARBAGE COL. — FVGs mitigados por el cuerpo se eliminan.
      4. GATILLO      — Triple confluencia (solo en sesión):
                        Toque FVG + Sweep flag activo + Absorción.

    Condiciones de entrada (las 3 deben cumplirse):
      ┌──────────────────────────────────────────────────────┐
      │  A) El precio toca la zona del FVG activo            │
      │  B) sweep_bull_cooldown > 0 (o bear para shorts)     │
      │     = hubo un sweep estructural en las últimas N     │
      │       velas (default 8 = 40 min en M5)               │
      │  C) Absorción institucional en la vela:              │
      │     - Mecha de rechazo > 30% del rango               │
      │     - Volumen relativo > 1.1x la media               │
      └──────────────────────────────────────────────────────┘
    """

    # ── Parámetros Configurables ──────────────────────────────────
    SWEEP_COOLDOWN_VELAS = 8   # Velas de gracia post-sweep (~40 min en M5)

    def __init__(self, session_filter='NY'):
        self.session_filter = session_filter

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"⚙️ Radar de Zonas v2.1 (Memoria Espacial) | Sesión: {self.session_filter}")

        n = len(df)
        signals = np.zeros(n)

        # ── Memorias Espaciales Persistentes ──────────────────────
        active_bullish_fvgs = []     # {'top', 'bottom', 'idx'}
        active_bearish_fvgs = []     # {'top', 'bottom', 'idx'}
        active_swing_highs = []      # {'price', 'idx'}
        active_swing_lows = []       # {'price', 'idx'}

        # Cooldowns post-sweep (contadores de velas restantes)
        sweep_bull_cooldown = 0      # > 0 = sweep alcista reciente activo
        sweep_bear_cooldown = 0      # > 0 = sweep bajista reciente activo

        # ── Extracción a arrays NumPy (cero .iloc en el loop) ─────
        lows = df['low'].values
        highs = df['high'].values
        closes = df['close'].values

        fvgs_bull = df['fvg_bullish'].values
        fvgs_bear = df['fvg_bearish'].values

        is_sh = df['is_swing_high'].values
        is_sl = df['is_swing_low'].values
        pl_high_prices = df['pl_high_price'].values
        pl_low_prices = df['pl_low_price'].values

        wicks_down_pct = df['lower_wick_pct'].values
        wicks_up_pct = df['upper_wick_pct'].values
        vols_rel = df['vol_relative'].values

        # Filtro de sesión
        if self.session_filter == 'NY':
            sesion_activa = df['is_ny_session'].values
        elif self.session_filter == 'London':
            sesion_activa = df['is_london_session'].values
        elif self.session_filter == 'Asia':
            sesion_activa = df['is_asian_session'].values
        else:
            sesion_activa = np.ones(n)

        # Contadores para diagnóstico
        sweeps_bull_total = 0
        sweeps_bear_total = 0

        # ══════════════════════════════════════════════════════════
        #  LOOP PRINCIPAL
        # ══════════════════════════════════════════════════════════
        for i in range(2, n):

            # ── 1. REGISTRO DE ZONAS FVG (24/5) ─────────────────
            if fvgs_bull[i] == 1:
                active_bullish_fvgs.append({
                    'top': lows[i],
                    'bottom': highs[i - 2],
                    'idx': i,
                })

            if fvgs_bear[i] == 1:
                active_bearish_fvgs.append({
                    'top': lows[i - 2],
                    'bottom': highs[i],
                    'idx': i,
                })

            # ── 2. REGISTRO DE PUNTOS LÍQUIDOS (24/5) ───────────
            #    features.py marca is_swing_high=1 en la vela
            #    donde se CONFIRMA el swing. El precio real del
            #    PL viene en pl_high_price / pl_low_price.
            if is_sh[i] == 1 and not np.isnan(pl_high_prices[i]):
                active_swing_highs.append({
                    'price': pl_high_prices[i],
                    'idx': i,
                })

            if is_sl[i] == 1 and not np.isnan(pl_low_prices[i]):
                active_swing_lows.append({
                    'price': pl_low_prices[i],
                    'idx': i,
                })

            # ── 3. DETECCIÓN DE SWEEPS EN TIEMPO REAL ────────────
            #    Sweep Alcista (trampa para shorts):
            #      La mecha baja perfora un PL Low activo,
            #      pero el cuerpo cierra por ENCIMA del nivel.
            #      → Se elimina el PL (fue consumido)
            #      → Se activa el cooldown de sweep alcista.
            #
            #    Sweep Bajista (trampa para longs):
            #      La mecha sube perfora un PL High activo,
            #      pero el cuerpo cierra por DEBAJO del nivel.
            #      → Se elimina el PL + activa cooldown bajista.
            for pl in active_swing_lows[:]:
                if lows[i] < pl['price']:
                    if closes[i] > pl['price']:
                        # Sweep legítimo: barrió y recuperó
                        sweep_bull_cooldown = self.SWEEP_COOLDOWN_VELAS
                        sweeps_bull_total += 1
                    # En ambos casos (sweep o ruptura real), el PL
                    # fue tocado y deja de ser liquidez virgen
                    active_swing_lows.remove(pl)

            for pl in active_swing_highs[:]:
                if highs[i] > pl['price']:
                    if closes[i] < pl['price']:
                        # Sweep legítimo: barrió y recuperó
                        sweep_bear_cooldown = self.SWEEP_COOLDOWN_VELAS
                        sweeps_bear_total += 1
                    # PL consumido en ambos casos
                    active_swing_highs.remove(pl)

            # ── 4. GARBAGE COLLECTOR DE FVGs ─────────────────────
            #    FVG Alcista muere si el cuerpo cierra POR DEBAJO
            #    de su base (bottom). Mitigación completa.
            #    FVG Bajista muere si el cuerpo cierra POR ENCIMA
            #    de su techo (top). Mitigación completa.
            cierre = closes[i]
            active_bullish_fvgs = [
                fvg for fvg in active_bullish_fvgs
                if cierre >= fvg['bottom']
            ]
            active_bearish_fvgs = [
                fvg for fvg in active_bearish_fvgs
                if cierre <= fvg['top']
            ]

            # ── 5. GATILLO — Triple Confluencia ─────────────────
            #    Solo evalúa en la sesión configurada.
            if sesion_activa[i] != 1:
                # Decrementar cooldowns aunque no busquemos trades
                sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
                sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)
                continue

            # --- COMPRAS (Long) ---
            #  A) low[i] toca el techo del FVG alcista
            #  B) sweep_bull_cooldown > 0 (sweep reciente activo)
            #  C) mecha inferior > 30% + volumen > 1.1x
            if sweep_bull_cooldown > 0:
                for fvg in active_bullish_fvgs[:]:
                    if lows[i] <= fvg['top']:
                        if (wicks_down_pct[i] > 0.30
                                and vols_rel[i] > 1.1):
                            signals[i] = 1
                            active_bullish_fvgs.remove(fvg)
                            break

            # Si ya tomamos señal, no buscamos ventas
            if signals[i] != 0:
                sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
                sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)
                continue

            # --- VENTAS (Short) ---
            #  A) high[i] toca el piso del FVG bajista
            #  B) sweep_bear_cooldown > 0 (sweep reciente activo)
            #  C) mecha superior > 30% + volumen > 1.1x
            if sweep_bear_cooldown > 0:
                for fvg in active_bearish_fvgs[:]:
                    if highs[i] >= fvg['bottom']:
                        if (wicks_up_pct[i] > 0.30
                                and vols_rel[i] > 1.1):
                            signals[i] = -1
                            active_bearish_fvgs.remove(fvg)
                            break

            # ── Decremento de cooldowns al final de la vela ──────
            sweep_bull_cooldown = max(0, sweep_bull_cooldown - 1)
            sweep_bear_cooldown = max(0, sweep_bear_cooldown - 1)

        # ══════════════════════════════════════════════════════════
        #  SALIDA
        # ══════════════════════════════════════════════════════════
        df_out = df.copy()
        df_out['Signal'] = signals

        compras = int(np.sum(signals == 1))
        ventas = int(np.sum(signals == -1))
        fvg_vivos = len(active_bullish_fvgs) + len(active_bearish_fvgs)
        pl_vivos = len(active_swing_highs) + len(active_swing_lows)

        print(
            f"✅ Rastreo v2.1 completado.\n"
            f"   Señales -> 🟢 Compras: {compras} | 🔴 Ventas: {ventas}\n"
            f"   Sweeps detectados -> Alcistas: {sweeps_bull_total} | Bajistas: {sweeps_bear_total}\n"
            f"   Memoria al cierre -> FVGs vivos: {fvg_vivos} | PLs vivos: {pl_vivos}"
        )
        return df_out