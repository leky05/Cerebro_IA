import pandas as pd
import joblib
from sklearn.cluster import KMeans

print("1. Cargando datos de ENTRENAMIENTO avanzados (4 Dimensiones)...")
df_train = pd.read_csv("XAUUSD_M5_Train.csv", index_col="Datetime", parse_dates=True)

# AHORA LEEMOS LAS 4 COLUMNAS PARA TAPAR LOS PUNTOS CIEGOS
caracteristicas = df_train[['Distancia_SMA', 'Distancia_SMA_200', 'ATR_Relativo', 'RSI_14']]

print("2. Entrenando el cerebro matemático (K-Means)...")
modelo_kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
df_train['Regimen_Mercado'] = modelo_kmeans.fit_predict(caracteristicas)

print("3. Empaquetando y guardando la IA mejorada...")
joblib.dump(modelo_kmeans, 'modelo_kmeans_xauusd.pkl')

print("4. Resumen de los nuevos Regímenes (Visión Macro + Momentum):")
resumen = df_train.groupby('Regimen_Mercado')[['Distancia_SMA', 'Distancia_SMA_200', 'ATR_Relativo', 'RSI_14']].mean()
print(resumen)
print("\n¡Cerebro de 4 dimensiones entrenado y guardado con éxito como modelo_kmeans_xauusd.pkl!")