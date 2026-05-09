import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta  
import time
from datetime import datetime
import requests
import joblib
import os

from semaforo_cuantitativo import consultar_semaforo

# ==========================================
# CONFIGURACIÓN DEL DAEMON HÍBRIDO
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
LOTE_BASE = 0.01

CEREBROS_REVERSION = {}
CEREBROS_FAKEOUT = {}

# ==========================================
# FUNCIONES AUXILIARES Y DE RIESGO
# ==========================================
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

def abrir_operacion(symbol, tipo_orden, sl, tp, comentario):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None: return None
    precio = tick.ask if tipo_orden == mt5.ORDER_TYPE_BUY else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": LOTE_BASE,
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
    """Cálculo de riesgo para Reversión a la Media (Spread)"""
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
    """Cálculo de riesgo dinámico para Trampas de Liquidez (ATR)"""
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
# EXTRACCIÓN DE DATOS Y CARGA DE MODELOS
# ==========================================
def cargar_cerebros_ia():
    print("\n🧠 Iniciando carga de armamento algorítmico...")
    for p1, p2 in PARES_ACTIVOS:
        ruta = f"Data_Lake/Modelos_IA/Cerebro_{p1}_{p2}.pkl"
        if os.path.exists(ruta):
            CEREBROS_REVERSION[f"{p1}_{p2}"] = joblib.load(ruta)
            print(f"   ✅ Reversión {p1}-{p2} cargada.")

    for m in MONEDAS_INDIVIDUALES:
        ruta = f"Data_Lake/Modelos_IA/Fakeout_{m}.pkl"
        if os.path.exists(ruta):
            CEREBROS_FAKEOUT[m] = joblib.load(ruta)
            print(f"   ✅ Cazador Fakeout {m} cargado.")
    print("===================================================\n")

def extraer_datos_vivos(par):
    """Datos para el motor de Reversión (Spread, Z-Score)"""
    velas = mt5.copy_rates_from_pos(par, mt5.TIMEFRAME_H1, 0, VENTANA_Z_SCORE + 50)
    if velas is None: return None
    df = pd.DataFrame(velas)
    df.ta.rsi(length=14, append=True)
    media = df['close'].rolling(VENTANA_Z_SCORE).mean()
    std = df['close'].rolling(VENTANA_Z_SCORE).std()
    df['z_score'] = (df['close'] - media) / std
    return df

def extraer_datos_fakeout(par):
    """Datos para el motor de Fakeouts (Bollinger, ATR, Volumen)"""
    velas = mt5.copy_rates_from_pos(par, mt5.TIMEFRAME_H1, 0, 50)
    if velas is None: return None
    df = pd.DataFrame(velas)
    df.rename(columns={'tick_volume': 'volume'}, inplace=True)
    
    df.ta.bbands(length=20, std=2.0, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.rsi(length=14, append=True)
    vol_sma = df['volume'].rolling(20).mean()
    
    col_bbl = [c for c in df.columns if c.startswith('BBL')][0]
    col_bbu = [c for c in df.columns if c.startswith('BBU')][0]
    col_atr = [c for c in df.columns if c.startswith('ATR')][0]
    
    datos = {
        col_atr: df[col_atr].iloc[-1],
        'RSI_14': df['RSI_14'].iloc[-1],
        'ratio_volumen': df['volume'].iloc[-1] / vol_sma.iloc[-1],
        'distancia_bbu': df['close'].iloc[-1] - df[col_bbu].iloc[-1],
        'distancia_bbl': df['close'].iloc[-1] - df[col_bbl].iloc[-1]
    }
    return pd.DataFrame([datos])

# ==========================================
# EL CEREBRO PRINCIPAL (BUCLE DE EJECUCIÓN)
# ==========================================
def ejecutar_bot():
    print("🤖 Bot Quant Híbrido en línea.")
    cargar_cerebros_ia()
    
    if not mt5.initialize(): 
        print("❌ Error conectando a MT5")
        return
    
    enviar_telegram("🟢 Sistema Quant Híbrido iniciado. Armamento IA cargado y vigilando el mercado...")
    
    hora_ultima_revision = None
    while True:
        ahora = datetime.now()
        print(f"[{ahora.strftime('%H:%M:%S')}] ⏳ Escaneando mercado...", end="\r")
        
        if ahora.minute == 0 and hora_ultima_revision != ahora.hour:
            hora_ultima_revision = ahora.hour
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔔 Nueva vela. Analizando regímenes...")
            
            for p1, p2 in PARES_ACTIVOS:
                s1, s2 = consultar_semaforo(p1), consultar_semaforo(p2)
                
                # --- CASO A: RÉGIMEN DE TENDENCIA (Motor Fakeout) ---
                if "TENDENCIA" in s1['estado'] or "TENDENCIA" in s2['estado']:
                    print(f"   🚦 Semáforo en Tendencia. {p1}: {s1['icono']} | {p2}: {s2['icono']}")
                    
                    for m in [p1, p2]:
                        if m in CEREBROS_FAKEOUT:
                            if evitar_sobreexposicion(m): continue
                                
                            df_f = extraer_datos_fakeout(m)
                            if df_f is None: continue
                                
                            dist_bbu = df_f['distancia_bbu'].iloc[0]
                            dist_bbl = df_f['distancia_bbl'].iloc[0]
                            
                            # Condición de activación: El precio rompe las bandas de Bollinger
                            if dist_bbu > 0 or dist_bbl < 0:
                                prediccion = CEREBROS_FAKEOUT[m].predict(df_f)[0]
                                
                                if prediccion == 1:
                                    print(f"   🎯 ¡TRAMPA CONFIRMADA EN {m}! IA autoriza cacería.")
                                    riesgo = RIESGO_FAKEOUT[m]
                                    col_atr = [c for c in df_f.columns if c.startswith('ATR')][0]
                                    atr_actual = df_f[col_atr].iloc[0]
                                    
                                    if dist_bbu > 0:
                                        tipo_orden = mt5.ORDER_TYPE_SELL # Trampa Alcista -> Vendemos
                                    else:
                                        tipo_orden = mt5.ORDER_TYPE_BUY  # Trampa Bajista -> Compramos
                                        
                                    tick = mt5.symbol_info_tick(m)
                                    precio_actual = tick.ask if tipo_orden == mt5.ORDER_TYPE_BUY else tick.bid
                                    
                                    sl, tp = calcular_sl_tp_fakeout(m, tipo_orden, precio_actual, atr_actual, riesgo["sl_atr"], riesgo["tp_atr"])
                                    res = abrir_operacion(m, tipo_orden, sl, tp, "IA_Fakeout")
                                    
                                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                        msg = f"🦈 CAZADOR DE FAKEOUTS 🦈\nMoneda: {m}\nDirección: {'COMPRA' if tipo_orden == mt5.ORDER_TYPE_BUY else 'VENTA'}\n✅ IA detectó trampa de liquidez."
                                        enviar_telegram(msg)
                                        print(f"   💸 Orden ejecutada con éxito para {m}.")
                                    else:
                                        print(f"   ❌ Error ejecución Fakeout: {res.comment if res else 'N/A'}")

                # --- CASO B: RÉGIMEN DE RANGO (Motor Reversión) ---
                elif s1['estado'] == "RANGO_LATERAL" and s2['estado'] == "RANGO_LATERAL":
                    nombre_mod = f"{p1}_{p2}"
                    if nombre_mod in CEREBROS_REVERSION:
                        df1 = extraer_datos_vivos(p1)
                        df2 = extraer_datos_vivos(p2)
                        if df1 is None or df2 is None: continue
                        
                        z1, z2 = df1['z_score'].iloc[-1], df2['z_score'].iloc[-1]
                        rsi1, rsi2 = df1['RSI_14'].iloc[-1], df2['RSI_14'].iloc[-1]
                        spread_total = z1 + z2
                        
                        if abs(spread_total) > 1.5:
                            print(f"   🟢 Semáforo Rango. Anomalía en {p1}-{p2} | Spread: {spread_total:.2f}")
                            if evitar_sobreexposicion(p1, p2): continue 
                            
                            datos_ia = {'spread_total': spread_total, f'z_score_{p1}': z1, f'z_score_{p2}': z2, f'RSI_14_{p1}': rsi1, f'RSI_14_{p2}': rsi2}
                            modelo = CEREBROS_REVERSION[nombre_mod]
                            df_pred = pd.DataFrame([datos_ia])[modelo.feature_names_in_] 
                            
                            prediccion = modelo.predict(df_pred)[0]
                            if prediccion == 1:
                                print("   🎯 IA PRECUANTIFICA REVERSIÓN. Autoriza disparo...")
                                riesgo = RIESGO_PARES[nombre_mod]
                                precio1, std_p1 = df1['close'].iloc[-1], df1['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1]
                                precio2, std_p2 = df2['close'].iloc[-1], df2['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1]
                                
                                tipo1, tipo2 = (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL) if spread_total > 1.5 else (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY)
                                    
                                sl1, tp1 = calcular_sl_tp(p1, tipo1, precio1, std_p1, riesgo["sl"], riesgo["tp"])
                                sl2, tp2 = calcular_sl_tp(p2, tipo2, precio2, std_p2, riesgo["sl"], riesgo["tp"])
                                
                                res1 = abrir_operacion(p1, tipo1, sl1, tp1, "IA_Reversion")
                                res2 = abrir_operacion(p2, tipo2, sl2, tp2, "IA_Reversion")
                                
                                if res1 and res1.retcode == mt5.TRADE_RETCODE_DONE:
                                    msg = f"⚡ ARBITRAJE EJECUTADO ⚡\nPares: {p1} y {p2}\nSpread: {spread_total:.2f}\n✅ IA Confirma Reversión."
                                    enviar_telegram(msg)
                                    print(f"   💸 Órdenes enviadas con éxito para {p1}-{p2}.")
                            else:
                                print("   🛡️ IA rechaza la Reversión (Peligro Estadístico).")

        time.sleep(60)

if __name__ == "__main__":
    ejecutar_bot()