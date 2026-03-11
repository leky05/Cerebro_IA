import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import joblib
import sqlite3
import time
from datetime import datetime

print("--- SISTEMA INSTITUCIONAL ACTIVADO ---")
print("Cargando la IA 4D en memoria RAM...")
modelo_kmeans = joblib.load('modelo_kmeans_xauusd.pkl')
scaler = joblib.load('escalador_xauusd.pkl')

def analizar_mercado():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando escaneo de mercado...")
    
    if not mt5.initialize():
        print("❌ Error al iniciar MT5. Revisá que la plataforma esté abierta.")
        return

    simbolo_broker = "XAUUSD+" 
    velas_vivo = mt5.copy_rates_from_pos(simbolo_broker, mt5.TIMEFRAME_M5, 0, 300)

    if velas_vivo is None or len(velas_vivo) == 0:
        print(f"❌ ERROR: MetaTrader 5 no devolvió datos para '{simbolo_broker}'.")
        mt5.shutdown()
        return

    df_vivo = pd.DataFrame(velas_vivo)
    df_vivo['time'] = pd.to_datetime(df_vivo['time'], unit='s')
    df_vivo.rename(columns={'time': 'Date', 'tick_volume': 'volume'}, inplace=True)
    df_vivo.set_index('Date', inplace=True)

    df_vivo['SMA_20'] = df_vivo['close'].rolling(window=20).mean()
    df_vivo['SMA_200'] = df_vivo['close'].rolling(window=200).mean()

    df_vivo['High-Low'] = df_vivo['high'] - df_vivo['low']
    df_vivo['High-PrevClose'] = np.abs(df_vivo['high'] - df_vivo['close'].shift(1))
    df_vivo['Low-PrevClose'] = np.abs(df_vivo['low'] - df_vivo['close'].shift(1))
    df_vivo['TrueRange'] = df_vivo[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
    df_vivo['ATR_14'] = df_vivo['TrueRange'].rolling(window=14).mean()

    delta = df_vivo['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df_vivo['RSI_14'] = 100 - (100 / (1 + rs))

    ultima_vela = df_vivo.iloc[-2] 
    dist_sma_hoy = (ultima_vela['close'] - ultima_vela['SMA_20']) / ultima_vela['SMA_20'] * 100
    dist_sma_200_hoy = (ultima_vela['close'] - ultima_vela['SMA_200']) / ultima_vela['SMA_200'] * 100
    atr_rel_hoy = (ultima_vela['ATR_14'] / ultima_vela['close']) * 100
    rsi_hoy = ultima_vela['RSI_14']

    datos_hoy = pd.DataFrame({
        'Distancia_SMA': [dist_sma_hoy], 
        'Distancia_SMA_200': [dist_sma_200_hoy],
        'ATR_Relativo': [atr_rel_hoy],
        'RSI_14': [rsi_hoy]
    })

    datos_hoy_escalados = pd.DataFrame(scaler.transform(datos_hoy), columns=datos_hoy.columns)
    regimen_actual = modelo_kmeans.predict(datos_hoy_escalados)[0]

    print(f"--- ANÁLISIS M5 ---> RÉGIMEN ACTUAL: {regimen_actual}")

    # Guardar en SQLite (Diario)
    memoria = pd.DataFrame({
        'Fecha': [ultima_vela.name],
        'Precio_Cierre': [ultima_vela['close']],
        'Distancia_SMA': [dist_sma_hoy],
        'Distancia_SMA_200': [dist_sma_200_hoy],
        'ATR_Relativo': [atr_rel_hoy],
        'RSI_14': [rsi_hoy],
        'Regimen_Elegido': [regimen_actual]
    })
    conexion = sqlite3.connect("memoria_ia.db")
    memoria.to_sql('diario_de_operaciones', conexion, if_exists='append', index=False)
    conexion.close()

    # Guardar en MetaTrader (Pizarra)
    ruta_mt5 = r"C:\Users\lekys\AppData\Roaming\MetaQuotes\Terminal\AE2CC2E013FDE1E3CDF010AA51C60400\MQL5\Files\IA_Regimen.txt"
    with open(ruta_mt5, "w") as archivo:
        archivo.write(str(regimen_actual))

    mt5.shutdown()
    print("✅ Pizarra actualizada. Esperando próxima vela...\n")


# --- EL RELOJ INFINITO ---
print("⏰ Reloj iniciado. Sincronizando con las velas de 5 minutos...")
analizar_mercado() # Hacemos un primer escaneo apenas le das Play

while True:
    ahora = datetime.now()
    
    # Comprobamos si estamos exactamente en el minuto 0, 5, 10, 15... y en el segundo 1
    # Usamos el segundo 1 para darle un segundito al broker de cerrar la vela anterior
    if ahora.minute % 5 == 0 and ahora.second == 1:
        analizar_mercado()
        time.sleep(60) # Dormimos 1 minuto para que no vuelva a escanear en este mismo cierre
    else:
        time.sleep(1) # Miramos la hora cada 1 segundo