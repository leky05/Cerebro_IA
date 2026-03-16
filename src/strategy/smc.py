import pandas as pd
import numpy as np

class SMCStateMachine:
    """
    Rastreador de Zonas (Spatial Memory).
    Guarda los FVG en memoria permanente hasta que son mitigados.
    """
    def __init__(self, session_filter='NY'):
        self.session_filter = session_filter

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"⚙️ Iniciando Radar de Zonas Espaciales (Sesión: {self.session_filter})...")
        
        signals = np.zeros(len(df))
        
        # Cajas de memoria para Zonas Vivas (Listas de diccionarios)
        active_bullish_fvgs = []
        active_bearish_fvgs = []
        
        # Extracción rápida
        lows = df['low'].values
        highs = df['high'].values
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
            # 1. REGISTRO DE ZONAS (Ocurre 24/5, el mercado siempre deja huellas)
            if fvgs_bull[i] == 1:
                # El FVG Alcista se forma entre el High de hace 2 velas y el Low actual
                # NOTA: En la lógica real de pandas, esto se calculó en features.py
                # Aquí simplemente asumimos que si fvg_bullish == 1, la vela actual es la vela 3.
                top_fvg = df['low'].iloc[i]
                bottom_fvg = df['high'].iloc[i-2]
                active_bullish_fvgs.append({'top': top_fvg, 'bottom': bottom_fvg})
                
            if fvgs_bear[i] == 1:
                bottom_fvg = df['high'].iloc[i]
                top_fvg = df['low'].iloc[i-2]
                active_bearish_fvgs.append({'top': top_fvg, 'bottom': bottom_fvg})
            
            # 2. LIMPIEZA DE ZONAS (Mitigación)
            # Si el precio atraviesa un FVG por completo, lo borramos de la memoria
            # FVG Alcista invalidado si el precio cierra por debajo de su base
            active_bullish_fvgs = [fvg for fvg in active_bullish_fvgs if df['close'].iloc[i] > fvg['bottom']]
            # FVG Bajista invalidado si el precio cierra por encima de su techo
            active_bearish_fvgs = [fvg for fvg in active_bearish_fvgs if df['close'].iloc[i] < fvg['top']]

            # 3. GATILLO (Solo en la sesión permitida)
            if sesion_activa[i] == 1:
                
                # BUSCAR COMPRAS (Precio cayendo dentro de un FVG Alcista vivo)
                for fvg in active_bullish_fvgs:
                    # Si el precio mínimo tocó o penetró el FVG...
                    if lows[i] <= fvg['top']:
                        # ...y aparece el martillo con volumen
                        if wicks_down_pct[i] > 0.30 and vols_rel[i] > 1.1:
                            signals[i] = 1
                            # Una vez que dispara, asumimos zona mitigada (borramos para no sobre-operar)
                            active_bullish_fvgs.remove(fvg)
                            break # Solo un disparo por vela
                            
                # BUSCAR VENTAS (Precio subiendo dentro de un FVG Bajista vivo)
                for fvg in active_bearish_fvgs:
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