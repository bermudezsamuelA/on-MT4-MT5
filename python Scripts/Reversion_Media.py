import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta  # La magia cuantitativa

# ==========================================
# 1. PANEL DE CONTROL (Configuración)
# ==========================================
SIMBOLO = "EURUSD"
TEMPORALIDAD = mt5.TIMEFRAME_H1  # Cámbialo a mt5.TIMEFRAME_D1 para gráficos diarios
LOTE = 0.01
VELAS_HISTORIAL = 250  # Extraemos 250 para poder calcular la SMA de 200

# Parámetros Matemáticos
SMA_PERIOD = 200
BB_PERIOD = 20
BB_STD = 2.0
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# ==========================================
# 2. INICIALIZACIÓN
# ==========================================
if not mt5.initialize():
    print("Error al inicializar MT5")
    quit()

mt5.symbol_select(SIMBOLO, True)
info = mt5.symbol_info(SIMBOLO)
punto = info.point
# ==========================================
# 3. EXTRACCIÓN Y PROCESAMIENTO (El Cerebro)
# ==========================================
velas = mt5.copy_rates_from_pos(SIMBOLO, TEMPORALIDAD, 0, VELAS_HISTORIAL)
df = pd.DataFrame(velas)
df['time'] = pd.to_datetime(df['time'], unit='s')

df.ta.sma(length=SMA_PERIOD, append=True)
df.ta.bbands(length=BB_PERIOD, std=BB_STD, append=True)
df.ta.rsi(length=RSI_PERIOD, append=True)
df.dropna(inplace=True)

col_sma = [c for c in df.columns if c.startswith('SMA')][0]
col_bbl = [c for c in df.columns if c.startswith('BBL')][0] 
col_bbu = [c for c in df.columns if c.startswith('BBU')][0] 
col_bbm = [c for c in df.columns if c.startswith('BBM')][0] 
col_rsi = [c for c in df.columns if c.startswith('RSI')][0]

vela_actual = df.iloc[-2]
vela_anterior = df.iloc[-3]


# ---------------------------------------------------------
# EL TRADUCTOR HUMANO (Dashboard de Consola)
# ---------------------------------------------------------
# 1. Traducir Temporalidad
nombres_tf = {mt5.TIMEFRAME_M1: "M1", mt5.TIMEFRAME_M5: "M5", mt5.TIMEFRAME_M15: "M15", mt5.TIMEFRAME_H1: "H1", mt5.TIMEFRAME_H4: "H4", mt5.TIMEFRAME_D1: "D1"}
texto_tf = nombres_tf.get(TEMPORALIDAD, str(TEMPORALIDAD))

valor_promedio = vela_actual[col_sma]

# 2. Traducir SMA (Tendencia)
if vela_actual['close'] > valor_promedio:
    texto_sma = f"ALCISTA 🐂 (Precio actual [{vela_actual['close']}] > Promedio [{valor_promedio:.5f}]. Solo buscaremos Compras)."
else:
    texto_sma = f"BAJISTA 🐻 (Precio actual [{vela_actual['close']}] < Promedio [{valor_promedio:.5f}]. Solo buscaremos Ventas)."

# 3. Traducir Bollinger
if vela_actual['close'] <= vela_actual[col_bbl]:
    texto_bb = f"¡ZONA DE PÁNICO! (Rompió el piso de {vela_actual[col_bbl]:.5f}. Rebote alcista inminente)."
elif vela_actual['close'] >= vela_actual[col_bbu]:
    texto_bb = f"¡ZONA DE EUFORIA! (Rompió el techo de {vela_actual[col_bbu]:.5f}. Caída inminente)."
else:
    texto_bb = f"Zona de confort (Moviéndose entre el piso {vela_actual[col_bbl]:.5f} y el techo {vela_actual[col_bbu]:.5f})."

# 4. Traducir RSI
if vela_actual[col_rsi] < RSI_OVERSOLD:
    texto_rsi = "Sobrevendido (< 30): Mercado exhausto de caer. Riesgo de giro alcista."
elif vela_actual[col_rsi] > RSI_OVERBOUGHT:
    texto_rsi = "Sobrecomprado (> 70): Mercado exhausto de subir. Riesgo de giro bajista."
else:
    texto_rsi = "Neutral (30-70): Inercia normal, sin fuerza extrema."

print(f"\n=======================================================")
print(f"   📊 REPORTE DE MERCADO: {SIMBOLO} EN {texto_tf}")
print(f"=======================================================")
print(f"1. Precio Actual : {vela_actual['close']}")
print(f"2. Promedio SMA  : {valor_promedio:.5f}")
print(f"   -> Tendencia  : {texto_sma}")
print(f"3. Bollinger     : {texto_bb}")
print(f"4. RSI Actual    : {vela_actual[col_rsi]:.2f} -> {texto_rsi}")
print(f"=======================================================\n")

# ==========================================
# 4. MOTOR LÓGICO (Evaluación de Condiciones)
# ==========================================
orden_tipo = None
precio_entrada = 0.0
sl = 0.0
tp = 0.0

if vela_actual['close'] > vela_actual[col_sma]: 
    if vela_actual['low'] <= vela_actual[col_bbl] or vela_anterior['low'] <= vela_anterior[col_bbl]: 
        if vela_anterior[col_rsi] < RSI_OVERSOLD and vela_actual[col_rsi] >= RSI_OVERSOLD: 
            print(">>> ¡GATILLO ACTIVADO! SEÑAL DE COMPRA ENCONTRADA <<<")
            orden_tipo = mt5.ORDER_TYPE_BUY
            precio_entrada = mt5.symbol_info_tick(SIMBOLO).ask
            sl = vela_actual['low'] - (50 * punto) 
            tp = vela_actual[col_bbm] 

elif vela_actual['close'] < vela_actual[col_sma]: 
    if vela_actual['high'] >= vela_actual[col_bbu] or vela_anterior['high'] >= vela_anterior[col_bbu]: 
        if vela_anterior[col_rsi] > RSI_OVERBOUGHT and vela_actual[col_rsi] <= RSI_OVERBOUGHT: 
            print(">>> ¡GATILLO ACTIVADO! SEÑAL DE VENTA ENCONTRADA <<<")
            orden_tipo = mt5.ORDER_TYPE_SELL
            precio_entrada = mt5.symbol_info_tick(SIMBOLO).bid
            sl = vela_actual['high'] + (50 * punto) 
            tp = vela_actual[col_bbm] 

# ==========================================
# 5. EJECUCIÓN
# ==========================================
if orden_tipo is not None:
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SIMBOLO,
        "volume": LOTE,
        "type": orden_tipo,
        "price": precio_entrada,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 777,
        "comment": "Bot Reversion Media",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Error al enviar orden: {res.retcode}")
    else:
        print(f"✅ Operación Ejecutada. Ticket: {res.order}")
else:
    print("⏳ Diagnóstico del Bot: No hay anomalías explotables en este momento. Esperando próxima vela...\n")

mt5.shutdown()
