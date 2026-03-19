import os
import time
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5
import plotly.graph_objects as go
from dotenv import load_dotenv

# Importaciones locales de tu ecosistema
from src.features.features import SMCFeatureEngineer
from src.brain import CerebroIA
from src.telegram_bot.telegram_bot import TelegramNotifier
from src.executor import TraderMT5 # <--- NUEVO: El dedo en el gatillo

load_dotenv()

# --- CONFIGURACIÓN ---
SIMBOLO_ORO = "XAUUSD+" # Tu sufijo exacto
TEMPORALIDAD = mt5.TIMEFRAME_M5
BUFFER_COSTOS_VANTAGE = 0.30
RIESGO_POR_TRADE = 1.0 # Arriesga el 1% de tu cuenta Demo por operación

def obtener_velas_mt5(cantidad=100):
    """Extrae las últimas velas en vivo directo de MetaTrader 5"""
    if not mt5.initialize():
        print("❌ Error al conectar con MetaTrader 5. ¿Está abierto el programa?")
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

def generar_grafico_trade(df, fvg_data, decision, filename="temp_chart.png"):
    """Genera un clon visual de TradingView con Plotly y calcula los niveles exactos"""
    print("📊 Pintando el gráfico al estilo TradingView...")
    
    data_plot = df.tail(50).copy()
    data_plot.reset_index(inplace=True)
    
    precio_entrada = data_plot['close'].iloc[-1]
    tiempo_entrada = data_plot['time'].iloc[-1]
    
    tiempo_futuro = tiempo_entrada + pd.Timedelta(minutes=5 * 15)

    if fvg_data['trade_direction'] == 'long':
        sl = fvg_data['base_fvg'] - BUFFER_COSTOS_VANTAGE
        riesgo = precio_entrada - sl
        tp = precio_entrada + (riesgo * 2) 
        color_riesgo = 'rgba(242, 54, 69, 0.2)'    
        color_beneficio = 'rgba(8, 153, 129, 0.2)' 
    else:
        sl = fvg_data['techo_fvg'] + BUFFER_COSTOS_VANTAGE
        riesgo = sl - precio_entrada
        tp = precio_entrada - (riesgo * 2) 
        color_riesgo = 'rgba(242, 54, 69, 0.2)'
        color_beneficio = 'rgba(8, 153, 129, 0.2)'

    fig = go.Figure(data=[go.Candlestick(
        x=data_plot['time'],
        open=data_plot['open'], high=data_plot['high'],
        low=data_plot['low'], close=data_plot['close'],
        increasing_line_color='#089981', decreasing_line_color='#F23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#F23645'
    )])

    fig.add_shape(type="rect",
        x0=tiempo_entrada, y0=precio_entrada, x1=tiempo_futuro, y1=sl,
        fillcolor=color_riesgo, line_width=0, layer="below"
    )

    fig.add_shape(type="rect",
        x0=tiempo_entrada, y0=precio_entrada, x1=tiempo_futuro, y1=tp,
        fillcolor=color_beneficio, line_width=0, layer="below"
    )

    fig.update_layout(
        title=f"🐺 SABUESO: {fvg_data['tipo']} | Confianza: {decision.get('confidence', 'N/A')}",
        yaxis_title='Precio XAUUSD',
        xaxis_rangeslider_visible=False,
        template='plotly_white',
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        margin=dict(l=40, r=40, t=60, b=40)
    )

    fig.write_image(filename, width=1280, height=720, scale=2)
    
    # Devolvemos los niveles matemáticos para que el bot los ejecute en MT5
    return precio_entrada, sl, tp

def run_forward_tester():
    print("🚀 INICIANDO EJECUCIÓN AUTOMÁTICA EN DEMO (FASE 7) 🚀")
    
    ia = CerebroIA()
    telegram = TelegramNotifier()
    trader = TraderMT5(simbolo=SIMBOLO_ORO, riesgo_porcentaje=RIESGO_POR_TRADE) # Instanciamos al ejecutor
    
    telegram.enviar_mensaje("🟢 <b>MODO COMBATE ACTIVADO</b>\nMonitoreando XAUUSD+. Cerebro_IA tiene permisos para disparar órdenes en Demo.")
    
    alertas_enviadas = set()

    while True:
        hora_actual = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{hora_actual}] 📡 Escaneando el mercado...")
        
        df = obtener_velas_mt5()
        
        if df is not None:
            df = SMCFeatureEngineer.calculate_features(df)
            
            vela_cerrada = df.iloc[-2]
            indice_vela = len(df) - 2
            
            trade_analizado_esta_vela = False
            
            # --- 1. EVALUAR COMPRAS (LONG) ---
            if vela_cerrada.get('recent_sweep_bullish', 0) == 1 and not trade_analizado_esta_vela:
                for j in range(indice_vela - 30, indice_vela):
                    if df.get('fvg_bullish', pd.Series(0)).iloc[j] == 1:
                        techo_fvg = df['low'].iloc[j]
                        base_fvg = df['high'].iloc[j-2]
                        
                        if vela_cerrada['low'] <= techo_fvg and df.index[j] not in alertas_enviadas:
                            
                            fvg_data = {"trade_direction": "long", "tipo": "Alcista (Long)", "techo_fvg": round(techo_fvg, 2), "base_fvg": round(base_fvg, 2)}
                            
                            velas_json = [
                                {
                                    "vela": k-29, 
                                    "open": round(r['open'], 2), 
                                    "high": round(r['high'], 2), 
                                    "low": round(r['low'], 2), 
                                    "close": round(r['close'], 2),
                                    "vol_relative": round(r.get('vol_relative', 1.0), 2)
                                } 
                                for k, (idx, r) in enumerate(df.iloc[indice_vela-29:indice_vela+1].iterrows())
                            ]
                            
                            decision = ia.analizar_setup(fvg_data, velas_json)
                            
                            if decision.get('signal') == 1:
                                nombre_foto = "temp_chart.png"
                                # 1. Generar la foto y sacar los precios exactos
                                p_entrada, sl, tp = generar_grafico_trade(df, fvg_data, decision, filename=nombre_foto)
                                
                                # 2. ¡DISPARAR LA ORDEN AL BROKER!
                                exito, detalle = trader.ejecutar_orden("long", p_entrada, sl, tp)
                                
                                # 3. Armar el mensaje de Telegram incluyendo si la orden entró bien o no
                                msg = f"🟢 <b>NUEVA ENTRADA APROBADA (LONG)</b>\n\n📝 <b>Razonamiento:</b> <i>{decision.get('reasoning')}</i>\n\n"
                                msg += f"🤖 <b>Estado de Ejecución:</b> {'✅ APROBADO' if exito else '❌ FALLÓ'}\n<i>{detalle}</i>"
                                
                                telegram.enviar_foto(nombre_foto, msg)
                                
                                if os.path.exists(nombre_foto):
                                    os.remove(nombre_foto)
                                print("✅ Gráfico LONG y Orden enviados.")
                            else:
                                print(f"🛑 IA rechazó el Long. Motivo: {decision.get('reasoning', 'N/A')}")
                            
                            alertas_enviadas.add(df.index[j])
                            trade_analizado_esta_vela = True
                            break 

            # --- 2. EVALUAR VENTAS (SHORT) ---
            if vela_cerrada.get('recent_sweep_bearish', 0) == 1 and not trade_analizado_esta_vela:
                for j in range(indice_vela - 30, indice_vela):
                    if df.get('fvg_bearish', pd.Series(0)).iloc[j] == 1:
                        base_fvg = df['high'].iloc[j]
                        techo_fvg = df['low'].iloc[j-2]
                        
                        if vela_cerrada['high'] >= base_fvg and df.index[j] not in alertas_enviadas:
                            
                            fvg_data = {"trade_direction": "short", "tipo": "Bajista (Short)", "techo_fvg": round(techo_fvg, 2), "base_fvg": round(base_fvg, 2)}
                            
                            velas_json = [
                                {
                                    "vela": k-29, 
                                    "open": round(r['open'], 2), 
                                    "high": round(r['high'], 2), 
                                    "low": round(r['low'], 2), 
                                    "close": round(r['close'], 2),
                                    "vol_relative": round(r.get('vol_relative', 1.0), 2)
                                } 
                                for k, (idx, r) in enumerate(df.iloc[indice_vela-29:indice_vela+1].iterrows())
                            ]
                            
                            decision = ia.analizar_setup(fvg_data, velas_json)
                            
                            if decision.get('signal') == 1:
                                nombre_foto = "temp_chart.png"
                                p_entrada, sl, tp = generar_grafico_trade(df, fvg_data, decision, filename=nombre_foto)
                                
                                # ¡DISPARAR LA ORDEN AL BROKER!
                                exito, detalle = trader.ejecutar_orden("short", p_entrada, sl, tp)
                                
                                msg = f"🔴 <b>NUEVA ENTRADA APROBADA (SHORT)</b>\n\n📝 <b>Razonamiento:</b> <i>{decision.get('reasoning')}</i>\n\n"
                                msg += f"🤖 <b>Estado de Ejecución:</b> {'✅ APROBADO' if exito else '❌ FALLÓ'}\n<i>{detalle}</i>"
                                
                                telegram.enviar_foto(nombre_foto, msg)
                                
                                if os.path.exists(nombre_foto):
                                    os.remove(nombre_foto)
                                print("✅ Gráfico SHORT y Orden enviados.")
                            else:
                                print(f"🛑 IA rechazó el Short. Motivo: {decision.get('reasoning', 'N/A')}")
                            
                            alertas_enviadas.add(df.index[j])
                            trade_analizado_esta_vela = True
                            break 
            
        print("⏳ Durmiendo 5 minutos hasta el próximo cierre de vela de M5...")
        time.sleep(300) 

if __name__ == "__main__":
    run_forward_tester()