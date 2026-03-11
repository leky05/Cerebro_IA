import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib

print("1. Leyendo la data institucional de Dukascopy (SQ)...")
nombre_archivo_sq = "XAUUSD_dukascopy_nuevo-M5_historial.csv" # <-- REEMPLAZA ESTO
df = pd.read_csv(nombre_archivo_sq)

print("2. Formateando fechas y columnas...")
df['Datetime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
df.set_index('Datetime', inplace=True)
df.drop(['Date', 'Time'], axis=1, inplace=True)
df.columns = df.columns.str.lower()

print("3. Tapando Puntos Ciegos: Calculando Contexto Avanzado...")
# --- TENDENCIA MICRO Y MACRO ---
df['SMA_20'] = df['close'].rolling(window=20).mean()
df['SMA_200'] = df['close'].rolling(window=200).mean() # NUEVO: Visión Macro

# --- VOLATILIDAD (ATR) ---
df['High-Low'] = df['high'] - df['low']
df['High-PrevClose'] = np.abs(df['high'] - df['close'].shift(1))
df['Low-PrevClose'] = np.abs(df['low'] - df['close'].shift(1))
df['TrueRange'] = df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
df['ATR_14'] = df['TrueRange'].rolling(window=14).mean()
df.drop(['High-Low', 'High-PrevClose', 'Low-PrevClose', 'TrueRange'], axis=1, inplace=True)

# --- MOMENTUM (RSI 14) NUEVO ---
delta = df['close'].diff()
up = delta.clip(lower=0)
down = -1 * delta.clip(upper=0)
ema_up = up.ewm(com=13, adjust=False).mean()
ema_down = down.ewm(com=13, adjust=False).mean()
rs = ema_up / ema_down
df['RSI_14'] = 100 - (100 / (1 + rs))

# --- VARIABLES RELATIVAS PARA LA IA ---
df['Distancia_SMA'] = (df['close'] - df['SMA_20']) / df['SMA_20'] * 100
df['Distancia_SMA_200'] = (df['close'] - df['SMA_200']) / df['SMA_200'] * 100 # NUEVO
df['ATR_Relativo'] = (df['ATR_14'] / df['close']) * 100

# Limpiar los primeros 200 periodos que quedaron vacíos por culpa de la SMA 200
df.dropna(inplace=True)

print("4. Cortando la línea de tiempo (IS vs OOS)...")
train_data = df.loc['2018-05-01':'2024-12-31'].copy()
test_data = df.loc['2025-01-01':'2026-03-04'].copy()

print("5. Escalando las 4 dimensiones de forma segura...")
scaler = StandardScaler()

# AHORA LA IA ES DE 4 DIMENSIONES
caracteristicas = ['Distancia_SMA', 'Distancia_SMA_200', 'ATR_Relativo', 'RSI_14']

train_data[caracteristicas] = scaler.fit_transform(train_data[caracteristicas])
test_data[caracteristicas] = scaler.transform(test_data[caracteristicas])

print("6. Guardando los cerebros y el nuevo TRADUCTOR...")
train_data.to_csv("XAUUSD_M5_Train.csv")
test_data.to_csv("XAUUSD_M5_Test.csv")
joblib.dump(scaler, 'escalador_xauusd.pkl')

print("¡Listo! Datos enriquecidos, ceguera curada y archivos guardados.")