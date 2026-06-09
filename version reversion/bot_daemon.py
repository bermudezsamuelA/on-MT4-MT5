import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta  
import numpy as np
import time
from datetime import datetime
import requests
import joblib
import os

from semaforo_cuantitativo import consultar_semaforo

# ==========================================
# CONFIGURACIÓN DEL DAEMON HÍBRIDO (FASE 2)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8668581533:AAHjwwdTZ6Tylq8_w8dz-MqGySPUlIhyb3k")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1133179366")

PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"), ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"), ("EURUSD", "USDCHF"),
    ("NZDUSD", "USDCHF"), ("AUDUSD", "USDCAD")
]

MONEDAS_INDIVIDUALES = ["GBPUSD", "USDCAD", "USDCHF", "EURUSD", "NZDUSD", "AUDUSD"]

RIESGO_PARES = {
    "GBPUSD_USDCAD": {"sl": 0.78, "tp": 0.91}, "GBPUSD_USDCHF": {"sl": 0.50, "tp": 0.77},
    "EURUSD_USDCAD": {"sl": 0.63, "tp": 0.86}, "EURUSD_USDCHF": {"sl": 0.48, "tp": 0.78},
    "NZDUSD_USDCHF": {"sl": 0.52, "tp": 0.80}, "AUDUSD_USDCAD": {"sl": 0.46, "tp": 1.12}
}

RIESGO_FAKEOUT = {
    "GBPUSD": {"sl_atr": 1.2, "tp_atr": 2.4}, "USDCAD": {"sl_atr": 1.0, "tp_atr": 2.0},
    "USDCHF": {"sl_atr": 1.1, "tp_atr": 2.2}, "EURUSD": {"sl_atr": 1.0, "tp_atr": 2.0},
    "NZDUSD": {"sl_atr": 1.3, "tp_atr": 2.6}, "AUDUSD": {"sl_atr": 1.2, "tp_atr": 2.4}
}

VENTANA_Z_SCORE = 250

# 🛡️ PARÁMETROS INSTITUCIONALES 🛡️
RIESGO_POR_OPERACION = 1.0 
SPREAD_MAXIMO_PIPS = 3.0   

CEREBROS_REVERSION = {}
CEREBROS_FAKEOUT = {}

# ==========================================
# MÓDULOS DE SEGURIDAD, RIESGO Y LOGS
# ==========================================
def registrar_operacion_fantasma(simbolo, motivo, motor):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{fecha}] 👻 FANTASMA | {motor} | {simbolo} | Bloqueado por: {motivo}\n"
    ruta_log = "Data_Lake/operaciones_fantasma.log"
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(linea)

def spread_es_seguro(symbol, max_pips=SPREAD_MAXIMO_PIPS):
    info = mt5.symbol_info(symbol)
    if info is None: return False, 0
    spread_pips = info.spread / 10.0 
    return spread_pips <= max_pips, spread_pips

def calcular_lotaje_dinamico(symbol, precio_entrada, sl_precio, riesgo_porcentaje=RIESGO_POR_OPERACION):
    info = mt5.symbol_info(symbol)
    cuenta = mt5.account_info()
    
    if info is None or cuenta is None: 
        return 0.01 
        
    riesgo_dinero = cuenta.margin_free * (riesgo_porcentaje / 100.0)
    distancia_sl = abs(precio_entrada - sl_precio)
    if distancia_sl == 0: return info.volume_min
    
    tick_value = info.trade_tick_value
    tick_size = info.trade_tick_size
    perdida_por_un_lote = (distancia_sl / tick_size) * tick_value
    
    if perdida_por_un_lote == 0: return info.volume_min
    
    lotes_calculados = riesgo_dinero / perdida_por_un_lote
    lotes = round(lotes_calculados / info.volume_step) * info.volume_step
    
    if lotes < info.volume_min: lotes = info.volume_min
    if lotes > info.volume_max: lotes = info.volume_max
    
    return round(lotes, 2)

def validar_micro_tendencia_m15(simbolo, tipo_orden):
    velas_m15 = mt5.copy_rates_from_pos(simbolo, mt5.TIMEFRAME_M15, 0, 50)
    if velas_m15 is None: return False
    
    df_m15 = pd.DataFrame(velas_m15)
    df_m15.ta.ema(length=20, append=True)
    df_m15.dropna(inplace=True)
    if df_m15.empty: return False
    
    precio_actual = df_m15['close'].iloc[-1]
    col_ema = [c for c in df_m15.columns if c.startswith('EMA')][0]
    ema_20_m15 = df_m15[col_ema].iloc[-1]
    
    if tipo_orden == mt5.ORDER_TYPE_BUY:
        return precio_actual > ema_20_m15 
    else:
        return precio_actual < ema_20_m15 

def evitar_sobreexposicion(par1, par2=None):
    posiciones = mt5.positions_get()
    if not posiciones: return False
    simbolos_abiertos = [pos.symbol for pos in posiciones]
    if par2:
        return par1 in simbolos_abiertos or par2 in simbolos_abiertos
    return par1 in simbolos_abiertos

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje})
    except Exception: pass

def abrir_operacion(symbol, tipo_orden, volumen, sl, tp, comentario):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return None
    precio = tick.ask if tipo_orden == mt5.ORDER_TYPE_BUY else tick.bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volumen, 
        "type": tipo_orden,
        "price": precio,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": 9999,
        "comment": comentario,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    return mt5.order_send(request)

def calcular_sl_tp(symbol, tipo_orden, precio_actual, std_dev, mult_sl, mult_tp):
    info = mt5.symbol_info(symbol)
    if info is None: return 0, 0
    distancia_sl = std_dev * mult_sl
    distancia_tp = std_dev * mult_tp
    if tipo_orden == mt5.ORDER_TYPE_BUY:
        tp = precio_actual + distancia_tp
        sl = precio_actual - distancia_sl
    else: 
        tp = precio_actual - distancia_tp
        sl = precio_actual + distancia_sl
    return round(sl, info.digits), round(tp, info.digits)


def calcular_sl_tp_fakeout(symbol, tipo_orden, precio_actual, atr, mult_sl, mult_tp):
    """Calcula el riesgo dinámico basado en el ATR de la vela de trampa."""
    info = mt5.symbol_info(symbol)
    if info is None: return 0, 0
    
    distancia_sl = atr * mult_sl
    distancia_tp = atr * mult_tp
    
    if tipo_orden == mt5.ORDER_TYPE_BUY:
        tp = precio_actual + distancia_tp
        sl = precio_actual - distancia_sl
    else:
        tp = precio_actual - distancia_tp
        sl = precio_actual + distancia_sl
        
    return round(sl, info.digits), round(tp, info.digits)
# ==========================================
# EXTRACCIÓN Y COINTEGRACIÓN (EL CEREBRO)
# ==========================================
def cargar_cerebros_ia():
    print("\n🧠 Iniciando carga de armamento algorítmico...")
    for p1, p2 in PARES_ACTIVOS:
        ruta = f"Data_Lake/Modelos_IA/Cerebro_{p1}_{p2}.pkl"
        if os.path.exists(ruta):
            CEREBROS_REVERSION[f"{p1}_{p2}"] = joblib.load(ruta)
            print(f"   ✅ Reversión Cointegrada {p1}-{p2} cargada.")
    for m in MONEDAS_INDIVIDUALES:
        ruta = f"Data_Lake/Modelos_IA/Fakeout_{m}.pkl"
        if os.path.exists(ruta):
            CEREBROS_FAKEOUT[m] = joblib.load(ruta)
            print(f"   ✅ Cazador Fakeout {m} cargado.")
    print("===================================================\n")

def extraer_datos_cointegracion(par1, par2):
    """
    Motor de Fase 2: Lee los precios vivos y los fusiona en tiempo real
    usando Logaritmos y el Hedge Ratio (Beta) para el Arbitraje.
    """
    velas1 = mt5.copy_rates_from_pos(par1, mt5.TIMEFRAME_H1, 0, VENTANA_Z_SCORE + 50)
    velas2 = mt5.copy_rates_from_pos(par2, mt5.TIMEFRAME_H1, 0, VENTANA_Z_SCORE + 50)
    
    if velas1 is None or velas2 is None: return None
    
    df1 = pd.DataFrame(velas1)
    df2 = pd.DataFrame(velas2)
    
    df1['time'] = pd.to_datetime(df1['time'], unit='s')
    df2['time'] = pd.to_datetime(df2['time'], unit='s')
    
    df1.ta.rsi(length=14, append=True)
    df2.ta.rsi(length=14, append=True)
    
    df1.rename(columns={'close': f'close_{par1}', 'RSI_14': f'RSI_14_{par1}'}, inplace=True)
    df2.rename(columns={'close': f'close_{par2}', 'RSI_14': f'RSI_14_{par2}'}, inplace=True)
    
    df_fusion = pd.merge(df1[['time', f'close_{par1}', f'RSI_14_{par1}']], 
                         df2[['time', f'close_{par2}', f'RSI_14_{par2}']], 
                         on='time', how='inner')
                         
    if df_fusion.empty: return None
    
    # 1. Transformación logarítmica
    log_p1 = np.log(df_fusion[f'close_{par1}'])
    log_p2 = np.log(df_fusion[f'close_{par2}'])
    
    # 2. Cálculo rodante del Hedge Ratio (Beta)
    covarianza = log_p1.rolling(window=VENTANA_Z_SCORE).cov(log_p2)
    varianza = log_p2.rolling(window=VENTANA_Z_SCORE).var()
    df_fusion['beta'] = covarianza / varianza
    
    # 3. Spread Residual Real
    df_fusion['spread_residual'] = log_p1 - (df_fusion['beta'] * log_p2)
    
    # 4. Z-Score del Spread Residual (El gatillo)
    media_spread = df_fusion['spread_residual'].rolling(window=VENTANA_Z_SCORE).mean()
    std_spread = df_fusion['spread_residual'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion['spread_total'] = (df_fusion['spread_residual'] - media_spread) / std_spread
    
    # 5. Cálculos para SL/TP de riesgo (Varianza pura del precio base)
    df_fusion[f'std_pura_{par1}'] = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion[f'std_pura_{par2}'] = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).std()

    # 6. Z-Scores individuales para alimentar a la IA
    media_p1 = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).mean()
    df_fusion[f'z_score_{par1}'] = (df_fusion[f'close_{par1}'] - media_p1) / df_fusion[f'std_pura_{par1}']
    
    media_p2 = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).mean()
    df_fusion[f'z_score_{par2}'] = (df_fusion[f'close_{par2}'] - media_p2) / df_fusion[f'std_pura_{par2}']
    
    df_fusion.dropna(inplace=True)
    if df_fusion.empty: return None
    
    # Retornamos únicamente la fila viva del presente
    return df_fusion.iloc[-1] 

def extraer_datos_fakeout(par):
    velas = mt5.copy_rates_from_pos(par, mt5.TIMEFRAME_H1, 0, 250)
    if velas is None: return None
    df = pd.DataFrame(velas)
    df.rename(columns={'tick_volume': 'volume'}, inplace=True)
    
    df.ta.bbands(length=20, std=2.0, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.ema(length=200, append=True) 
    vol_sma = df['volume'].rolling(20).mean()
    
    col_bbl = [c for c in df.columns if c.startswith('BBL')][0]
    col_bbu = [c for c in df.columns if c.startswith('BBU')][0]
    col_atr = [c for c in df.columns if c.startswith('ATR')][0]
    col_ema = [c for c in df.columns if c.startswith('EMA')][0]
    
    datos = {
        col_atr: df[col_atr].iloc[-1],
        'RSI_14': df['RSI_14'].iloc[-1],
        'ratio_volumen': df['volume'].iloc[-1] / vol_sma.iloc[-1],
        'distancia_bbu': df['close'].iloc[-1] - df[col_bbu].iloc[-1],
        'distancia_bbl': df['close'].iloc[-1] - df[col_bbl].iloc[-1],
        'ema_200': df[col_ema].iloc[-1] 
    }
    return pd.DataFrame([datos])

# ==========================================
# CEREBRO CENTRAL (BUCLE DE EJECUCIÓN)
# ==========================================
def ejecutar_bot():
    print("🤖 Bot Quant Híbrido en línea.")
    cargar_cerebros_ia()
    
    if not mt5.initialize(): 
        print("❌ Error conectando a MT5")
        return
    
    enviar_telegram("🟢 Sistema Quant Híbrido iniciado.\n✅ Cointegración Lineal (β)\n✅ Validación MTF (M15)\n✅ Filtro de Spread Institucional")
    
    hora_ultima_revision = None
    while True:
        ahora = datetime.now()
        print(f"[{ahora.strftime('%H:%M:%S')}] ⏳ Escaneando mercado...", end="\r")
        
        if ahora.minute == 0 and hora_ultima_revision != ahora.hour:
            hora_ultima_revision = ahora.hour
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔔 Nueva vela. Analizando regímenes...")
            
            for p1, p2 in PARES_ACTIVOS:
                s1, s2 = consultar_semaforo(p1), consultar_semaforo(p2)
                
                # ==========================================
                # CASO A: TENDENCIA (MOTOR FAKEOUT)
                # ==========================================
                # ==========================================
                # CASO A: TENDENCIA (MOTOR FAKEOUT)
                # ==========================================
                if "TENDENCIA" in s1['estado'] or "TENDENCIA" in s2['estado']:
                    print(f"   🚦 Semáforo en Tendencia. {p1}: {s1['icono']} | {p2}: {s2['icono']}")
                    
                    # 👇 AGREGA ESTA LÍNEA AQUÍ PARA APAGAR EL DISPARO 👇
                    print("   🛡️ Motor Fakeout en mantenimiento. Ignorando tendencia.")
                    continue                     
                    for m in [p1, p2]:
                        if m in CEREBROS_FAKEOUT:
                            if evitar_sobreexposicion(m): continue
                                
                            df_f = extraer_datos_fakeout(m)
                            if df_f is None: continue
                                
                            dist_bbu = df_f['distancia_bbu'].iloc[0]
                            dist_bbl = df_f['distancia_bbl'].iloc[0]
                            ema_200 = df_f['ema_200'].iloc[0]
                            
                            if dist_bbu > 0 or dist_bbl < 0:
                                prediccion = CEREBROS_FAKEOUT[m].predict(df_f.drop(columns=['ema_200']))[0]
                                
                                if prediccion == 1:
                                    tick = mt5.symbol_info_tick(m)
                                    if tick is None: continue
                                        
                                    if dist_bbu > 0:
                                        tipo_orden = mt5.ORDER_TYPE_SELL 
                                        precio_actual = tick.bid
                                    else:
                                        tipo_orden = mt5.ORDER_TYPE_BUY  
                                        precio_actual = tick.ask
                                    
                                    # 🛡️ FILTRO EMA 200 (MACRO)
                                    if tipo_orden == mt5.ORDER_TYPE_SELL and precio_actual > ema_200:
                                        registrar_operacion_fantasma(m, "Bloqueo EMA 200 (Tendencia Alcista)", "Fakeout")
                                        continue
                                    if tipo_orden == mt5.ORDER_TYPE_BUY and precio_actual < ema_200:
                                        registrar_operacion_fantasma(m, "Bloqueo EMA 200 (Tendencia Bajista)", "Fakeout")
                                        continue

                                    # 🔬 FILTRO MULTI-TIMEFRAME (MICRO M15)
                                    if not validar_micro_tendencia_m15(m, tipo_orden):
                                        motivo = "Micro-tendencia M15 en contra (Falta Momentum)"
                                        print(f"   🛑 {motivo}. Abortando disparo.")
                                        registrar_operacion_fantasma(m, motivo, "Fakeout")
                                        continue

                                    # 🛡️ FILTRO DE SPREAD
                                    seguro, spread_actual = spread_es_seguro(m)
                                    if not seguro:
                                        motivo = f"Spread Abierto ({spread_actual:.1f} > {SPREAD_MAXIMO_PIPS} pips)"
                                        print(f"   🛑 {motivo}. Abortando disparo.")
                                        registrar_operacion_fantasma(m, motivo, "Fakeout")
                                        continue

                                    riesgo = RIESGO_FAKEOUT[m]
                                    col_atr = [c for c in df_f.columns if c.startswith('ATR')][0]
                                    atr_actual = df_f[col_atr].iloc[0]
                                    
                                    sl, tp = calcular_sl_tp_fakeout(m, tipo_orden, precio_actual, atr_actual, riesgo["sl_atr"], riesgo["tp_atr"])
                                    
                                    # 📈 PARIDAD DE RIESGO
                                    volumen_exacto = calcular_lotaje_dinamico(m, precio_actual, sl)
                                    
                                    res = abrir_operacion(m, tipo_orden, volumen_exacto, sl, tp, "IA_Fakeout")
                                    
                                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                        msg = f"🦈 FAKEOUT 🦈\nMoneda: {m}\nDir: {'COMPRA' if tipo_orden == mt5.ORDER_TYPE_BUY else 'VENTA'}\nLotes: {volumen_exacto}\n✅ M15 Confirmado\n✅ Spread: {spread_actual:.1f}p"
                                        enviar_telegram(msg)
                                        print(f"   💸 Orden ejecutada. Lote calculado: {volumen_exacto}.")

                # ==========================================
                # CASO B: RANGO (MOTOR REVERSIÓN COINTEGRADA)
                # ==========================================
                elif s1['estado'] == "RANGO_LATERAL" and s2['estado'] == "RANGO_LATERAL":
                    nombre_mod = f"{p1}_{p2}"
                    if nombre_mod in CEREBROS_REVERSION:
                        
                        # Extraemos los datos de H1 fusionados vía Regresión Lineal
                        foto_actual = extraer_datos_cointegracion(p1, p2)
                        if foto_actual is None: continue
                        
                        spread_total = foto_actual['spread_total']
                        z1 = foto_actual[f'z_score_{p1}']
                        z2 = foto_actual[f'z_score_{p2}']
                        rsi1 = foto_actual[f'RSI_14_{p1}']
                        rsi2 = foto_actual[f'RSI_14_{p2}']
                        
                        if abs(spread_total) > 1.5:
                            print(f"   🟢 Semáforo Rango. Anomalía Residual en {p1}-{p2} | Spread: {spread_total:.2f}")
                            if evitar_sobreexposicion(p1, p2): continue 
                            
                            datos_ia = {'spread_total': spread_total, f'z_score_{p1}': z1, f'z_score_{p2}': z2, f'RSI_14_{p1}': rsi1, f'RSI_14_{p2}': rsi2}
                            modelo = CEREBROS_REVERSION[nombre_mod]
                            df_pred = pd.DataFrame([datos_ia])[modelo.feature_names_in_] 
                            
                            prediccion = modelo.predict(df_pred)[0]
                            if prediccion == 1:
                                
                                tipo1, tipo2 = (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL) if spread_total > 1.5 else (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY)

                                # 🔬 FILTRO MULTI-TIMEFRAME DUAL (M15)
                                mtf_p1 = validar_micro_tendencia_m15(p1, tipo1)
                                mtf_p2 = validar_micro_tendencia_m15(p2, tipo2)
                                if not mtf_p1 or not mtf_p2:
                                    motivo = f"Micro-tendencia M15 dividida (P1:{mtf_p1}, P2:{mtf_p2})"
                                    print(f"   🛑 {motivo}. Abortando Arbitraje.")
                                    registrar_operacion_fantasma(nombre_mod, motivo, "Reversion")
                                    continue

                                # 🛡️ FILTRO DE SPREAD DUAL
                                seg1, spr1 = spread_es_seguro(p1)
                                seg2, spr2 = spread_es_seguro(p2)
                                
                                if not seg1 or not seg2:
                                    motivo = f"Spread Abierto (P1:{spr1:.1f}p, P2:{spr2:.1f}p)"
                                    print(f"   🛑 {motivo}. Abortando Arbitraje.")
                                    registrar_operacion_fantasma(nombre_mod, motivo, "Reversion")
                                    continue

                                riesgo = RIESGO_PARES[nombre_mod]
                                
                                # Extraemos precios y desviaciones puras para el cálculo del Stop Loss
                                precio1 = foto_actual[f'close_{p1}']
                                std_p1 = foto_actual[f'std_pura_{p1}']
                                precio2 = foto_actual[f'close_{p2}']
                                std_p2 = foto_actual[f'std_pura_{p2}']
                                
                                sl1, tp1 = calcular_sl_tp(p1, tipo1, precio1, std_p1, riesgo["sl"], riesgo["tp"])
                                sl2, tp2 = calcular_sl_tp(p2, tipo2, precio2, std_p2, riesgo["sl"], riesgo["tp"])
                                
                                vol1 = calcular_lotaje_dinamico(p1, precio1, sl1, riesgo_porcentaje=RIESGO_POR_OPERACION/2)
                                vol2 = calcular_lotaje_dinamico(p2, precio2, sl2, riesgo_porcentaje=RIESGO_POR_OPERACION/2)
                                
                                res1 = abrir_operacion(p1, tipo1, vol1, sl1, tp1, "IA_Reversion")
                                res2 = abrir_operacion(p2, tipo2, vol2, sl2, tp2, "IA_Reversion")
                                
                                if res1 and res1.retcode == mt5.TRADE_RETCODE_DONE:
                                    msg = f"⚡ ARBITRAJE COINTEGRADO ⚡\nPares: {p1} / {p2}\nSpread Residual: {spread_total:.2f}\nLotes: {vol1} / {vol2}\n✅ M15 Confirmado"
                                    enviar_telegram(msg)
                                    print(f"   💸 Órdenes enviadas. Volúmenes: {vol1} y {vol2}.")

        time.sleep(60)

if __name__ == "__main__":
    ejecutar_bot()