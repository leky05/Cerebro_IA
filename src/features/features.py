import pandas as pd
import numpy as np


class SMCFeatureEngineer:
    """
    Motor de Características Institucional v2.2 — Cerebro_IA
    =========================================================
    Responsabilidad ÚNICA: calcular features matemáticas puras
    a partir del precio crudo. No toma decisiones de estado.

    Features generadas:
      - Filtro de sesiones (NY / London / Asia)
      - Microestructura de vela (mechas, cuerpo, volumen relativo)
      - Fair Value Gaps (FVG)
      - Puntos Líquidos: en qué vela se CONFIRMA un Swing High/Low
        y a qué precio exacto ocurrió.

    IMPORTANTE — Separación de responsabilidades:
      features.py  →  DETECTA swings y FVGs (matemática pura).
      smc.py       →  PERSISTE zonas en memoria espacial,
                       detecta sweeps en tiempo real, y evalúa
                       confluencia para disparar señales.
    """

    # ── Parámetros Configurables ──────────────────────────────────
    SWING_LOOKBACK = 10        # Velas a cada lado para confirmar un swing
    VOL_SMA_PERIOD = 10        # Período de la SMA de volumen

    # ──────────────────────────────────────────────────────────────
    #  MÉTODO PRINCIPAL
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
        print("👁️ Activando visión institucional SMC v2.2 (Features puras)...")
        df_feat = df.copy()

        # ==========================================================
        # 1. EL RELOJ — Filtro de Sesiones (UTC)
        # ==========================================================
        hour_utc = df_feat.index.hour
        df_feat['is_ny_session'] = np.where(
            (hour_utc >= 13) & (hour_utc < 16), 1, 0
        )
        df_feat['is_london_session'] = np.where(
            (hour_utc >= 7) & (hour_utc < 10), 1, 0
        )
        df_feat['is_asian_session'] = np.where(
            (hour_utc >= 0) & (hour_utc < 3), 1, 0
        )

        # ==========================================================
        # 2. MICROESTRUCTURA DE LA VELA
        #    Cálculos 100 % vectorizados con arrays NumPy
        # ==========================================================
        o = df_feat['open'].values
        h = df_feat['high'].values
        l = df_feat['low'].values
        c = df_feat['close'].values

        body_size = np.abs(c - o)
        total_range = h - l
        safe_range = np.where(total_range == 0, 1e-9, total_range)

        max_oc = np.maximum(o, c)
        min_oc = np.minimum(o, c)

        df_feat['body_size'] = body_size
        df_feat['total_range'] = total_range
        df_feat['upper_wick'] = h - max_oc
        df_feat['lower_wick'] = min_oc - l
        df_feat['upper_wick_pct'] = (h - max_oc) / safe_range
        df_feat['lower_wick_pct'] = (min_oc - l) / safe_range

        # ==========================================================
        # 3. VOLUMEN RELATIVO — Confirmación Institucional
        #    shift(1) para evitar data leakage
        # ==========================================================
        period = SMCFeatureEngineer.VOL_SMA_PERIOD
        vol_sma = df_feat['volume'].shift(1).rolling(window=period).mean()
        df_feat['vol_relative'] = df_feat['volume'] / (vol_sma + 1e-9)

        # ==========================================================
        # 4. FAIR VALUE GAPS (FVG) — Ineficiencias de precio
        # ==========================================================
        df_feat['fvg_bullish'] = np.where(
            df_feat['low'] > df_feat['high'].shift(2), 1, 0
        )
        df_feat['fvg_bearish'] = np.where(
            df_feat['high'] < df_feat['low'].shift(2), 1, 0
        )

        # ==========================================================
        # 5. PUNTOS LÍQUIDOS — Swing Highs / Lows
        #    Lookback configurable (default 10 velas a cada lado).
        #
        #    Lógica anti-lookahead:
        #      1. rolling(center=True) identifica el máximo/mínimo
        #         real en una ventana de (2*LB + 1) velas.
        #      2. shift(LB) retrasa la confirmación LB velas,
        #         garantizando que el swing solo aparece cuando
        #         ya existe toda la información a ambos lados.
        #
        #    Columnas de salida:
        #      is_swing_high  = 1 en la vela donde se CONFIRMA
        #      pl_high_price  = precio exacto del Swing High
        #      is_swing_low   = 1 en la vela donde se CONFIRMA
        #      pl_low_price   = precio exacto del Swing Low
        #
        #    smc.py consume estas columnas para registrar los PLs
        #    en memoria espacial permanente.
        # ==========================================================
        lb = SMCFeatureEngineer.SWING_LOOKBACK
        window = 2 * lb + 1

        rolling_max = df_feat['high'].rolling(window=window, center=True).max()
        rolling_min = df_feat['low'].rolling(window=window, center=True).min()

        swing_high_raw = (df_feat['high'] == rolling_max).astype(int)
        swing_low_raw = (df_feat['low'] == rolling_min).astype(int)

        df_feat['is_swing_high'] = swing_high_raw.shift(lb).fillna(0).astype(int)
        df_feat['is_swing_low'] = swing_low_raw.shift(lb).fillna(0).astype(int)

        # Precio exacto del PL (la vela origen está LB posiciones atrás)
        df_feat['pl_high_price'] = np.where(
            df_feat['is_swing_high'] == 1, df_feat['high'].shift(lb), np.nan
        )
        df_feat['pl_low_price'] = np.where(
            df_feat['is_swing_low'] == 1, df_feat['low'].shift(lb), np.nan
        )

        # ==========================================================
        # LIMPIEZA FINAL
        # ==========================================================
        df_feat.dropna(subset=['vol_relative'], inplace=True)

        n_sh = int(df_feat['is_swing_high'].sum())
        n_sl = int(df_feat['is_swing_low'].sum())
        print(
            f"✅ Features v2.2 listas. "
            f"Velas: {len(df_feat)} | "
            f"Swing Highs: {n_sh} | Swing Lows: {n_sl}"
        )
        return df_feat


# ══════════════════════════════════════════════════════════════
#  PRUEBA DE DIAGNÓSTICO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🛠️ Probando el Escáner SMC v2.2...")

    fechas = pd.date_range(
        '2024-01-02 13:00:00', periods=250, freq='5min', tz='UTC'
    )
    np.random.seed(42)

    base = 2050.0
    returns = np.random.normal(0, 0.5, 250)
    prices = base + np.cumsum(returns)

    datos_prueba = pd.DataFrame({
        'open': prices,
        'high': prices + np.random.uniform(0.3, 1.5, 250),
        'low': prices - np.random.uniform(0.3, 1.5, 250),
        'close': prices + np.random.normal(0, 0.3, 250),
        'volume': np.random.randint(100, 2000, 250),
    }, index=fechas)

    datos_con_features = SMCFeatureEngineer.calculate_features(datos_prueba)

    print("\n📊 COLUMNAS DISPONIBLES:")
    print(datos_con_features.columns.tolist())

    n_fvg_b = int(datos_con_features['fvg_bullish'].sum())
    n_fvg_s = int(datos_con_features['fvg_bearish'].sum())
    print(f"\n📊 FVGs -> Alcistas: {n_fvg_b} | Bajistas: {n_fvg_s}")

    print("\n📊 MUESTRA (Última vela):")
    print(datos_con_features.tail(1).T)