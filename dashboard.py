import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. Configuración de la página (Tema oscuro por defecto en Streamlit)
st.set_page_config(
    page_title="Cerebro_IA Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Título principal
st.title("🧠 Cerebro_IA | Centro de Comando Algorítmico")
st.markdown("Monitor de operativa en tiempo real y análisis de backtest para XAUUSD.")

# --- SIMULACIÓN DE DATOS (Luego conectaremos esto a TimescaleDB/PostgreSQL) ---
# Aquí irían tus queries reales con psycopg2 o SQLAlchemy
current_balance = 10000.00
current_equity = 10045.50
win_rate = 65.5
total_trades = 142

# 3. Panel de Métricas Principales (KPIs)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Current Balance", value=f"${current_balance:,.2f}")
with col2:
    st.metric(label="Current Equity", value=f"${current_equity:,.2f}", delta=f"${current_equity - current_balance:,.2f}")
with col3:
    st.metric(label="Win Rate", value=f"{win_rate}%", delta="2.1%", delta_color="normal")
with col4:
    st.metric(label="Total Trades", value=total_trades)

st.divider()

# 4. Gráfico Principal: Curva de Equity (Usando Plotly)
st.subheader("📊 Rendimiento del Sistema (Live vs Backtest)")

# Generamos datos dummy para el ejemplo
fechas = pd.date_range(start="2026-03-01", periods=18, freq="D")
equity_curve = np.cumsum(np.random.randn(18) * 50) + 10000

fig = go.Figure()
fig.add_trace(go.Scatter(x=fechas, y=equity_curve, mode='lines', name='Live Equity', line=dict(color='#00ffcc', width=2)))
# Aquí podrías superponer la curva del backtest generado con Dukascopy
# fig.add_trace(go.Scatter(x=fechas, y=backtest_curve, mode='lines', name='Backtest', line=dict(color='gray', dash='dash')))

fig.update_layout(
    template="plotly_dark",
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis_title="Fecha",
    yaxis_title="Capital ($)"
)
st.plotly_chart(fig, use_container_width=True)

# 5. Panel Inferior: Salud del Sistema y Filtros
col_izq, col_der = st.columns([1, 2])

with col_izq:
    st.subheader("⚙️ System Health")
    st.success("Conexión PostgreSQL: Activa")
    st.success("Vantage Broker API: Sincronizada")
    st.info("Telegram Bot: Esperando nueva señal...")

with col_der:
    st.subheader("🔍 Últimas Operaciones (XAUUSD)")
    # Simulación de un DataFrame que vendría de tu base de datos
    df_trades = pd.DataFrame({
        "Fecha": pd.date_range(start="2026-03-17", periods=4, freq="h"),
        "Dirección": ["Long", "Short", "Long", "Long"],
        "Lote": [0.1, 0.1, 0.2, 0.1],
        "Modelo/Lógica": ["XGBoost_v2", "MeanReversion", "XGBoost_v2", "XGBoost_v2"],
        "PnL": [45.0, -12.5, 80.0, 15.0]
    })
    st.dataframe(df_trades, use_container_width=True, hide_index=True)