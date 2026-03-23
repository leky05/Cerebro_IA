import os
import time
import numpy as np
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5
import plotly.graph_objects as go
from dotenv import load_dotenv

# Importaciones locales de tu ecosistema
from src.features.features import SMCFeatureEngineer
from src.brain import CerebroIA
from src.telegram_bot.telegram_bot import TelegramNotifier
from src.executor import TraderMT5
from src.trade_logger import TradeLogger

load_dotenv()

# --- CONFIGURACIÓN ---
SIMBOLO_ORO = "XAUUSD+"
TEMPORALIDAD = mt5.TIMEFRAME_M5
BUFFER_COSTOS_VANTAGE = 0.30
RIESGO_POR_TRADE = 1.0

# Alineado con smc.py y run_backtest.py
SWEEP_COOLDOWN_VELAS = 16  # ~80 min en M5
FVG_MIN_SIZE = 3.0         # Ignorar FVGs menores a 3 pts (ruido)


# ═══════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES (intactas del original)
# ═══════════════════════════════════════════════════════════════

def obtener_velas_mt5(cantidad=100):
    """Extrae las últimas velas en vivo directo de MetaTrader 5."""
    if not mt5.initialize():
        print(
            "❌ Error al conectar con MetaTrader 5. "
            "¿Está abierto el programa?"
        )
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
    """Genera un clon visual de TradingView con Plotly y calcula los
    niveles exactos de entrada, SL y TP."""
    print("📊 Pintando el gráfico al estilo TradingView...")

    data_plot = df.tail(50).copy()
    data_plot.reset_index(inplace=True)

    precio_entrada = data_plot['close'].iloc[-1]
    tiempo_entrada = data_plot['time'].iloc[-1]
    tiempo_futuro = tiempo_entrada + pd.Timedelta(minutes=5 * 15)

    # SL detrás de la mecha de la vela señal (última cerrada)
    vela_senal = data_plot.iloc[-1]
    if fvg_data['trade_direction'] == 'long':
        sl = vela_senal['low'] - BUFFER_COSTOS_VANTAGE
        riesgo = precio_entrada - sl
        tp = precio_entrada + (riesgo * 2)
        color_riesgo = 'rgba(242, 54, 69, 0.2)'
        color_beneficio = 'rgba(8, 153, 129, 0.2)'
    else:
        sl = vela_senal['high'] + BUFFER_COSTOS_VANTAGE
        riesgo = sl - precio_entrada
        tp = precio_entrada - (riesgo * 2)
        color_riesgo = 'rgba(242, 54, 69, 0.2)'
        color_beneficio = 'rgba(8, 153, 129, 0.2)'

    fig = go.Figure(data=[go.Candlestick(
        x=data_plot['time'],
        open=data_plot['open'], high=data_plot['high'],
        low=data_plot['low'], close=data_plot['close'],
        increasing_line_color='#089981', decreasing_line_color='#F23645',
        increasing_fillcolor='#089981', decreasing_fillcolor='#F23645',
    )])

    fig.add_shape(
        type="rect",
        x0=tiempo_entrada, y0=precio_entrada,
        x1=tiempo_futuro, y1=sl,
        fillcolor=color_riesgo, line_width=0, layer="below",
    )
    fig.add_shape(
        type="rect",
        x0=tiempo_entrada, y0=precio_entrada,
        x1=tiempo_futuro, y1=tp,
        fillcolor=color_beneficio, line_width=0, layer="below",
    )

    fig.update_layout(
        title=(
            f"🐺 SABUESO: {fvg_data['tipo']} | "
            f"Confianza: {decision.get('confidence', 'N/A')}"
        ),
        yaxis_title='Precio XAUUSD',
        xaxis_rangeslider_visible=False,
        template='plotly_white',
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        margin=dict(l=40, r=40, t=60, b=40),
    )

    fig.write_image(filename, width=1280, height=720, scale=2)

    return precio_entrada, sl, tp


# ═══════════════════════════════════════════════════════════════
# FUNCIÓN DE ANÁLISIS + EJECUCIÓN EN BROKER
# ═══════════════════════════════════════════════════════════════

def ejecutar_analisis_forward(
    ia, df, indice, fvg, direccion, etiqueta_tipo,
    trader, telegram, logger, cooldown_restante=0
):
    """
    Envía el setup a CerebroIA y, si aprueba, ejecuta en el broker.
    Registra TODA decisión (aprobada o rechazada) en el logger.

    Retorna:
      - dict con _cuota_agotada=True → cuota diaria agotada
      - True  → trade ejecutado (IA aprobó)
      - False → trade rechazado (IA dijo no)
    """
    # Armar bloque de 30 velas para la IA
    inicio_bloque = max(0, indice - 29)
    bloque = df.iloc[inicio_bloque:indice + 1]
    velas_json = [
        {
            "vela": j,
            "open": round(r['open'], 2),
            "high": round(r['high'], 2),
            "low": round(r['low'], 2),
            "close": round(r['close'], 2),
            "vol_relative": round(r.get('vol_relative', 1.0), 2),
        }
        for j, (_, r) in enumerate(bloque.iterrows())
    ]

    fvg_payload = {
        "trade_direction": direccion,
        "tipo": etiqueta_tipo,
        "techo_fvg": round(fvg['top'], 2),
        "base_fvg": round(fvg['bottom'], 2),
    }

    # ── Llamada a CerebroIA (blindado por Módulo 4) ───────────
    decision = ia.analizar_setup(fvg_payload, velas_json)

    # Propagar señal de cuota agotada
    if decision.get('_cuota_agotada'):
        return decision

    signal = decision.get('signal', 0)
    reasoning = decision.get('reasoning', 'N/A')

    if signal == 1:
        nombre_foto = "temp_chart.png"

        # 1. Generar gráfico y obtener niveles exactos
        p_entrada, sl, tp = generar_grafico_trade(
            df, fvg_payload, decision, filename=nombre_foto
        )

        # 2. Disparar orden al broker (Vantage/MT5)
        exito, detalle = trader.ejecutar_orden(
            direccion, p_entrada, sl, tp
        )

        # 3. Extraer ticket si se ejecutó
        ticket = None
        if exito and "Ticket:" in str(detalle):
            ticket = str(detalle).split("Ticket:")[1].split("|")[0].strip()

        # 4. Registrar trade APROBADO en log
        logger.registrar(
            timestamp_vela=df.index[indice],
            direccion=direccion,
            signal=1,
            reasoning=reasoning,
            fvg_top=fvg['top'],
            fvg_bottom=fvg['bottom'],
            precio_entrada=p_entrada,
            sl=sl,
            tp=tp,
            ejecutado=exito,
            ticket=ticket,
            cooldown_restante=cooldown_restante,
        )

        # 5. Notificación por Telegram
        emoji = "🟢" if direccion == "long" else "🔴"
        msg = (
            f"{emoji} <b>NUEVA ENTRADA APROBADA "
            f"({direccion.upper()})</b>\n\n"
            f"📝 <b>Razonamiento:</b> "
            f"<i>{reasoning}</i>\n\n"
            f"🎯 <b>Entrada:</b> {round(p_entrada, 2)} | "
            f"<b>SL:</b> {round(sl, 2)} | <b>TP:</b> {round(tp, 2)}\n\n"
            f"🤖 <b>Estado de Ejecución:</b> "
            f"{'✅ APROBADO' if exito else '❌ FALLÓ'}\n"
            f"<i>{detalle}</i>"
        )
        telegram.enviar_foto(nombre_foto, msg)

        if os.path.exists(nombre_foto):
            os.remove(nombre_foto)

        print(f"✅ Gráfico {direccion.upper()} y Orden enviados.")
        return True

    # ── Trade RECHAZADO: también se registra ────────────────
    logger.registrar(
        timestamp_vela=df.index[indice],
        direccion=direccion,
        signal=0,
        reasoning=reasoning,
        fvg_top=fvg['top'],
        fvg_bottom=fvg['bottom'],
        cooldown_restante=cooldown_restante,
    )

    print(
        f"🛑 IA rechazó el {direccion.upper()}. "
        f"Motivo: {reasoning}"
    )
    return False


# ═══════════════════════════════════════════════════════════════
# LOOP PRINCIPAL — Forward Tester con Memoria Espacial
# ═══════════════════════════════════════════════════════════════

def run_forward_tester():
    """
    Cerebro_IA Forward Tester v2.0 — Memoria Espacial Persistente
    ==============================================================
    A diferencia de la versión anterior, la memoria de FVGs, PLs
    y cooldowns se instancia AFUERA del while True. Cada ciclo
    de 5 minutos actualiza el estado existente en lugar de
    recalcularlo desde cero.

    Primer ciclo  → Bootstrap: procesa ~98 velas históricas para
                    construir la memoria inicial.
    Ciclos siguientes → Solo procesa la(s) vela(s) nueva(s) desde
                        la última marca de agua.
    """
    print("🚀 INICIANDO EJECUCIÓN AUTOMÁTICA EN DEMO (FASE 7) 🚀")

    # ── Instancias de servicios ───────────────────────────────
    try:
        ia = CerebroIA()
    except Exception as e:
        print(f"❌ Error al iniciar Cerebro_IA: {e}")
        return

    telegram = TelegramNotifier()
    trader = TraderMT5(
        simbolo=SIMBOLO_ORO, riesgo_porcentaje=RIESGO_POR_TRADE
    )
    logger = TradeLogger()
    print(f"📝 Trade Logger activo → {logger.log_file}")

    telegram.enviar_mensaje(
        "🟢 <b>MODO COMBATE ACTIVADO</b>\n"
        "Monitoreando XAUUSD+. Cerebro_IA tiene permisos para "
        "disparar órdenes en Demo."
    )

    # ═══════════════════════════════════════════════════════════
    # MEMORIA ESPACIAL PERSISTENTE (sobrevive entre ciclos)
    # ═══════════════════════════════════════════════════════════
    active_bullish_fvgs = []      # {'top', 'bottom', 'creacion'}
    active_bearish_fvgs = []      # {'top', 'bottom', 'creacion'}
    active_swing_highs = []       # PLs mayores {'price', 'timestamp'}
    active_swing_lows = []        # PLs mayores {'price', 'timestamp'}
    active_swing_highs_minor = [] # PLs menores {'price', 'timestamp'}
    active_swing_lows_minor = []  # PLs menores {'price', 'timestamp'}

    sweep_cooldown = 0  # Unificado: cualquier PL eliminado activa el contexto

    ultima_vela_procesada = None  # Marca de agua temporal
    cuota_agotada = False

    # ═══════════════════════════════════════════════════════════
    # LOOP PRINCIPAL — Un ciclo cada 5 minutos (cierre de vela)
    # ═══════════════════════════════════════════════════════════
    while True:
        hora_actual = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{hora_actual}] 📡 Escaneando el mercado...")

        # ── Check de cuota ────────────────────────────────────
        if cuota_agotada:
            print("   🚫 Cuota de API agotada. Bot en espera.")
            time.sleep(300)
            continue

        # ── 1. Descargar velas ────────────────────────────────
        df = obtener_velas_mt5()
        if df is None:
            print("⏳ Sin datos de MT5. Reintentando en 5 min...")
            time.sleep(300)
            continue

        # ── 2. Calcular features SMC ──────────────────────────
        try:
            df = SMCFeatureEngineer.calculate_features(df)
        except Exception as e:
            print(f"   ❌ Error en cálculo de features: {e}")
            time.sleep(300)
            continue

        # ── 3. Extraer arrays para velocidad ──────────────────
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

        # ── 4. Determinar rango de velas nuevas ──────────────
        # iloc[-1] es la vela EN FORMACIÓN → nunca se procesa.
        # Procesamos hasta iloc[-2] inclusive (última cerrada).
        indice_fin = len(df) - 1  # Exclusivo (range stop)

        if ultima_vela_procesada is None:
            # Bootstrap: procesar toda la historia disponible
            indice_inicio = 2  # Mínimo lookback para FVG (i-2)
            print(
                f"   🔧 Bootstrap: procesando "
                f"{indice_fin - indice_inicio} velas históricas "
                f"para construir Memoria Espacial..."
            )
        else:
            # Incremental: solo velas posteriores a la marca
            mask_nuevas = df.index > ultima_vela_procesada
            if not mask_nuevas.any():
                print("   ℹ️ Sin velas nuevas cerradas. Esperando...")
                time.sleep(300)
                continue
            indice_inicio = int(np.argmax(mask_nuevas))
            # Garantizar lookback válido para FVG
            if indice_inicio < 2:
                indice_inicio = 2

        # ══════════════════════════════════════════════════════
        # LOOP DE ACTUALIZACIÓN DE MEMORIA + GATILLO
        # Réplica exacta de la lógica de run_backtest.py:
        #   Registrar FVGs → Registrar PLs → Detectar Sweeps →
        #   GC de FVGs → Evaluar Gatillo → Decrementar Cooldowns
        # ══════════════════════════════════════════════════════
        for i in range(indice_inicio, indice_fin):

            # ──────────────────────────────────────────────────
            # A. REGISTRO DE ZONAS FVG
            # ──────────────────────────────────────────────────
            if fvgs_bull[i] == 1:
                size = lows[i] - highs[i - 2]
                if size >= FVG_MIN_SIZE:
                    active_bullish_fvgs.append({
                        'top': lows[i],
                        'bottom': highs[i - 2],
                        'creacion': df.index[i],
                    })
            if fvgs_bear[i] == 1:
                size = lows[i - 2] - highs[i]
                if size >= FVG_MIN_SIZE:
                    active_bearish_fvgs.append({
                        'top': lows[i - 2],
                        'bottom': highs[i],
                        'creacion': df.index[i],
                    })

            # ──────────────────────────────────────────────────
            # B. REGISTRO DE PUNTOS LÍQUIDOS (Mayores + Menores)
            # ──────────────────────────────────────────────────
            if is_sh[i] == 1 and not np.isnan(pl_high_prices[i]):
                active_swing_highs.append({
                    'price': pl_high_prices[i],
                    'timestamp': df.index[i],
                })
            if is_sl_arr[i] == 1 and not np.isnan(pl_low_prices[i]):
                active_swing_lows.append({
                    'price': pl_low_prices[i],
                    'timestamp': df.index[i],
                })
            if is_sh_minor[i] == 1 and not np.isnan(pl_high_prices_minor[i]):
                active_swing_highs_minor.append({
                    'price': pl_high_prices_minor[i],
                    'timestamp': df.index[i],
                })
            if is_sl_minor[i] == 1 and not np.isnan(pl_low_prices_minor[i]):
                active_swing_lows_minor.append({
                    'price': pl_low_prices_minor[i],
                    'timestamp': df.index[i],
                })

            # ──────────────────────────────────────────────────
            # C. ELIMINACIÓN DE PLs (cualquier breach activa
            #    el contexto — sin filtro de cierre)
            # ──────────────────────────────────────────────────
            for pl in active_swing_lows[:]:
                if lows[i] < pl['price']:
                    sweep_cooldown = SWEEP_COOLDOWN_VELAS
                    active_swing_lows.remove(pl)

            for pl in active_swing_lows_minor[:]:
                if lows[i] < pl['price']:
                    sweep_cooldown = SWEEP_COOLDOWN_VELAS
                    active_swing_lows_minor.remove(pl)

            for pl in active_swing_highs[:]:
                if highs[i] > pl['price']:
                    sweep_cooldown = SWEEP_COOLDOWN_VELAS
                    active_swing_highs.remove(pl)

            for pl in active_swing_highs_minor[:]:
                if highs[i] > pl['price']:
                    sweep_cooldown = SWEEP_COOLDOWN_VELAS
                    active_swing_highs_minor.remove(pl)

            # ──────────────────────────────────────────────────
            # D. GARBAGE COLLECTOR DE FVGs
            # ──────────────────────────────────────────────────
            cierre = closes[i]
            active_bullish_fvgs = [
                fvg for fvg in active_bullish_fvgs
                if cierre >= fvg['bottom']
            ]
            active_bearish_fvgs = [
                fvg for fvg in active_bearish_fvgs
                if cierre <= fvg['top']
            ]

            # ──────────────────────────────────────────────────
            # E. GATILLO — Solo en la ÚLTIMA vela cerrada
            #    (Confluencia: PL eliminado + FVG mitigado
            #     + Confirmación de IA)
            #    La dirección la define el tipo de FVG:
            #      FVG Bullish mitigado → Long
            #      FVG Bearish mitigado → Short
            # ──────────────────────────────────────────────────
            es_ultima_vela_cerrada = (i == indice_fin - 1)

            if es_ultima_vela_cerrada and sweep_cooldown > 0 and not cuota_agotada:
                trade_analizado = False

                # --- COMPRAS (Long): precio mitiga FVG Bullish ---
                if not trade_analizado:
                    for fvg in active_bullish_fvgs[:]:
                        if lows[i] <= fvg['top']:
                            print(f"\n{'=' * 50}")
                            print(
                                f"🐺 [SABUESO] Setup Alcista "
                                f"detectado en: {df.index[i]}"
                            )

                            resultado = ejecutar_analisis_forward(
                                ia, df, i, fvg, "long",
                                "Alcista (Long)", trader, telegram,
                                logger, sweep_cooldown,
                            )
                            trade_analizado = True

                            if (
                                isinstance(resultado, dict)
                                and resultado.get('_cuota_agotada')
                            ):
                                cuota_agotada = True

                            active_bullish_fvgs.remove(fvg)
                            break

                # --- VENTAS (Short): precio mitiga FVG Bearish ---
                if not trade_analizado and not cuota_agotada:
                    for fvg in active_bearish_fvgs[:]:
                        if highs[i] >= fvg['bottom']:
                            print(f"\n{'=' * 50}")
                            print(
                                f"🐺 [SABUESO] Setup Bajista "
                                f"detectado en: {df.index[i]}"
                            )

                            resultado = ejecutar_analisis_forward(
                                ia, df, i, fvg, "short",
                                "Bajista (Short)", trader, telegram,
                                logger, sweep_cooldown,
                            )
                            trade_analizado = True

                            if (
                                isinstance(resultado, dict)
                                and resultado.get('_cuota_agotada')
                            ):
                                cuota_agotada = True

                            active_bearish_fvgs.remove(fvg)
                            break

            # ──────────────────────────────────────────────────
            # F. DECREMENTO DE COOLDOWNS (una vez por cada vela)
            # ──────────────────────────────────────────────────
            sweep_cooldown = max(0, sweep_cooldown - 1)

        # ── Actualizar marca de agua temporal ─────────────────
        if indice_fin > 0:
            ultima_vela_procesada = df.index[indice_fin - 1]

        # ── Diagnóstico de estado ─────────────────────────────
        total_sh = len(active_swing_highs) + len(active_swing_highs_minor)
        total_sl = len(active_swing_lows) + len(active_swing_lows_minor)
        print(
            f"   📊 Memoria Espacial: "
            f"{len(active_bullish_fvgs)} FVG↑ | "
            f"{len(active_bearish_fvgs)} FVG↓ | "
            f"{total_sh} SH ({len(active_swing_highs)}M+{len(active_swing_highs_minor)}m) | "
            f"{total_sl} SL ({len(active_swing_lows)}M+{len(active_swing_lows_minor)}m) | "
            f"CD={sweep_cooldown}"
        )

        print(
            "⏳ Durmiendo 5 minutos hasta el próximo cierre "
            "de vela M5..."
        )
        time.sleep(300)


if __name__ == "__main__":
    run_forward_tester()