import pandas as pd
import numpy as np

class SMCStateMachine:
    """
    Rastreador de Zonas (Spatial Memory).
    Guarda los FVG en memoria permanente hasta que son mitigados por el cuerpo de una vela.
    """
    def __init__(self, session_filter='NY'):
        self.session_filter = session_filter

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"⚙️ Iniciando Radar de Zonas Espaciales (Sesión: {self.session_filter})...")
        
        signals = np.zeros(len(df))
        
        # Cajas de memoria para Zonas Vivas (Listas de diccionarios)
        active_bullish_fvgs = []
        active_bearish_fvgs = []
        
        # Extracción rápida (evitamos usar .iloc dentro del bucle para máximo rendimiento)
        lows = df['low'].values
        highs = df['high'].values
        closes = df['close'].values  # <-- Añadido para la limpieza rápida
        fvgs_bull = df['fvg_bullish'].values
        fvgs_bear = df['fvg_bearish'].values
        
        wicks_down_pct = df['lower_wick_pct'].values
        wicks_up_pct = df['upper_wick_pct'].values
        vols_rel = df['vol_relative'].values
        
        if self.session_filter == 'NY': sesion_activa = df['is_ny_session'].values
        elif self.session_filter == 'London': sesion_activa = df['is_london_session'].values
        elif self.session_filter == 'Asia': sesion_activa = df['is_asian_session'].values
        else: sesion_activa = np.ones(len(df))

        for i in range(len(df)):
            # 1. REGISTRO DE ZONAS (Ocurre 24/5)
            if fvgs_bull[i] == 1:
                top_fvg = lows[i]
                bottom_fvg = highs[i-2]
                active_bullish_fvgs.append({'top': top_fvg, 'bottom': bottom_fvg})
                
            if fvgs_bear[i] == 1:
                bottom_fvg = highs[i]
                top_fvg = lows[i-2]
                active_bearish_fvgs.append({'top': top_fvg, 'bottom': bottom_fvg})
            
            # 2. LIMPIEZA DE ZONAS (Mitigación Institucional)
            cierre_actual = closes[i]
            
            # FVG Alcista invalidado si el cuerpo cierra por DEBAJO de su base
            # (Conservamos solo si el cierre es mayor o igual al bottom)
            active_bullish_fvgs = [fvg for fvg in active_bullish_fvgs if cierre_actual >= fvg['bottom']]
            
            # FVG Bajista invalidado si el cuerpo cierra por ENCIMA de su techo
            # (Conservamos solo si el cierre es menor o igual al top)
            active_bearish_fvgs = [fvg for fvg in active_bearish_fvgs if cierre_actual <= fvg['top']]

            # 3. GATILLO (Solo en la sesión permitida)
            if sesion_activa[i] == 1:
                
                # BUSCAR COMPRAS (Iteramos sobre una copia [:] para poder usar .remove de forma segura)
                for fvg in active_bullish_fvgs[:]:
                    if lows[i] <= fvg['top']:
                        if wicks_down_pct[i] > 0.30 and vols_rel[i] > 1.1:
                            signals[i] = 1
                            active_bullish_fvgs.remove(fvg)
                            break 
                            
                # BUSCAR VENTAS (Iteramos sobre una copia [:])
                for fvg in active_bearish_fvgs[:]:
                    if highs[i] >= fvg['bottom']:
                        if wicks_up_pct[i] > 0.30 and vols_rel[i] > 1.1:
                            signals[i] = -1
                            active_bearish_fvgs.remove(fvg)
                            break

        df_out = df.copy()
        df_out['Signal'] = signals
        compras = int(np.sum(signals == 1))
        ventas = int(np.sum(signals == -1))
        print(f"✅ Rastreo completado. Set-Ups encontrados -> 🟢 Compras: {compras} | 🔴 Ventas: {ventas}")
        return df_out