import MetaTrader5 as mt5

class TraderMT5:
    """
    Módulo de Ejecución y Gestión de Riesgo Dinámica para Cerebro_IA.
    """
    def __init__(self, simbolo="XAUUSD+", riesgo_porcentaje=1.0):
        self.simbolo = simbolo
        self.riesgo = riesgo_porcentaje / 100.0 # Transforma 1.0 en 0.01 (1%)

    def calcular_lote(self, precio_entrada, sl):
        """Calcula el tamaño de la posición leyendo las reglas del broker"""
        account_info = mt5.account_info()
        symbol_info = mt5.symbol_info(self.simbolo)
        
        if account_info is None or symbol_info is None:
            print(f"❌ No se pudo acceder a la cuenta o al símbolo {self.simbolo}.")
            return 0.01
        
        balance = account_info.balance
        riesgo_usd = balance * self.riesgo # 1% del capital actual
        
        distancia_sl = abs(precio_entrada - sl)
        if distancia_sl == 0: 
            return symbol_info.volume_min
        
        # Extraemos el tamaño del contrato directamente de Vantage
        tamano_contrato = symbol_info.trade_contract_size
        
        # Fórmula Universal: Riesgo = Lotes * Tamaño Contrato * Distancia SL
        lotes = riesgo_usd / (tamano_contrato * distancia_sl)
        
        # Redondeamos a 2 decimales (estándar)
        lotes = round(lotes, 2)
        
        # Filtros de seguridad del broker (para no enviar una orden inválida)
        if lotes < symbol_info.volume_min: 
            lotes = symbol_info.volume_min
        elif lotes > symbol_info.volume_max: 
            lotes = symbol_info.volume_max
            
        return lotes

    def ejecutar_orden(self, direccion, precio, sl, tp):
        """Arma el paquete de datos y lo dispara al mercado"""
        lote = self.calcular_lote(precio, sl)
        tipo_orden = mt5.ORDER_TYPE_BUY if direccion == "long" else mt5.ORDER_TYPE_SELL
        
        print(f"⚙️ Orden {direccion.upper()} | Lotes calculados (1% riesgo): {lote} | SL: {sl} | TP: {tp}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.simbolo,
            "volume": lote,
            "type": tipo_orden,
            "price": precio,
            "sl": sl,
            "tp": tp,
            "deviation": 20, 
            "magic": 202603, 
            "comment": "Sabueso_IA",
            "type_time": mt5.ORDER_TIME_GTC, 
            "type_filling": mt5.ORDER_FILLING_IOC, 
        }
        
        resultado = mt5.order_send(request)
        
        if resultado.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Error al ejecutar trade: {resultado.comment} (Código: {resultado.retcode})")
            return False, resultado.comment
        else:
            print(f"✅ ¡TRADE EJECUTADO EN DEMO! Ticket: {resultado.order}")
            return True, f"Ticket: {resultado.order} | Lotes: {lote}"