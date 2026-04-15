import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import KMeans
import requests
import time
from datetime import datetime
from correlaciones_4h import obtener_espejos # Tu matriz personalizada

# ==========================================
# 1. PANEL DE CONTROL (Configuración)
# ==========================================
TOKEN = "ID DE CCHAT BOT"
CHAT_ID = "ID DE MI CHAT"

SIMBOLO = "EURUSD"
TEMPORALIDAD = mt5.TIMEFRAME_H1  
LOTE = 0.01

# Parámetros del Cerebro
SMA_PERIOD = 200
VELAS_ZONAS = 1000  
NUM_ZONAS = 12      
DISTANCIA_PICOS = 3 

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except:
        pass

def inicializar_mt5():
    if not mt5.initialize():
        print("Error al inicializar MT5")
        quit()
    mt5.symbol_select(SIMBOLO, True)
    print("✅ Conexión con MetaTrader 5 establecida.")

# ==========================================
# 2. EL CEREBRO: TENDENCIA + ZONAS K-MEANS
# ==========================================
def analizar_mercado():
    info = mt5.symbol_info(SIMBOLO)
    punto = info.point

    velas = mt5.copy_rates_from_pos(SIMBOLO, TEMPORALIDAD, 0, VELAS_ZONAS)
    if velas is None: return None, None

    df = pd.DataFrame(velas)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.ta.sma(length=SMA_PERIOD, append=True)
    df.dropna(inplace=True)

    col_sma = f'SMA_{SMA_PERIOD}'
    vela_actual = df.iloc[-2]
    vela_anterior = df.iloc[-3]
    timestamp_actual = vela_actual['time']

    # --- CALCULAR ZONAS INSTITUCIONALES ---
    idx_picos, _ = find_peaks(df['high'], distance=DISTANCIA_PICOS)
    idx_valles, _ = find_peaks(-df['low'], distance=DISTANCIA_PICOS)
    rebotes = np.concatenate((df['high'].iloc[idx_picos].values, df['low'].iloc[idx_valles].values))
    matriz_rebotes = rebotes.reshape(-1, 1)

    kmeans = KMeans(n_clusters=NUM_ZONAS, random_state=42, n_init=10).fit(matriz_rebotes)
    etiquetas = kmeans.labels_
    
    zonas = []
    for i in range(NUM_ZONAS):
        precios = matriz_rebotes[etiquetas == i].flatten()
        centroide = kmeans.cluster_centers_[i][0]
        desviacion = np.std(precios)
        zonas.append({"piso": centroide - desviacion, "techo": centroide + desviacion, "centro": centroide})

    # --- EVALUAR LÓGICA DE TREND FOLLOWING ---
    tendencia_alcista = vela_actual['close'] > vela_actual[col_sma]
    orden_tipo = None
    zona_gatillo = None
    sl, tp, precio_entrada = 0.0, 0.0, 0.0

    for zona in zonas:
        # ¿El precio tocó esta zona recientemente?
        toco_zona = (vela_anterior['low'] <= zona['techo'] and vela_anterior['high'] >= zona['piso']) or \
                    (vela_actual['low'] <= zona['techo'] and vela_actual['high'] >= zona['piso'])
        
        if toco_zona:
            zona_gatillo = zona
            # COMPRA: Tendencia Alcista + Precio tocó la zona (Soporte) + Vela actual cerró verde (Rebote)
            if tendencia_alcista and vela_actual['close'] > vela_actual['open']:
                orden_tipo = mt5.ORDER_TYPE_BUY
                precio_entrada = mt5.symbol_info_tick(SIMBOLO).ask
                sl = zona['piso'] - (100 * punto) # SL debajo de la caja
                tp = precio_entrada + (300 * punto) # TP fijo (o la próxima caja)
                break
            
            # VENTA: Tendencia Bajista + Precio tocó la zona (Resistencia) + Vela actual cerró roja (Rechazo)
            elif not tendencia_alcista and vela_actual['close'] < vela_actual['open']:
                orden_tipo = mt5.ORDER_TYPE_SELL
                precio_entrada = mt5.symbol_info_tick(SIMBOLO).bid
                sl = zona['techo'] + (100 * punto) # SL encima de la caja
                tp = precio_entrada - (300 * punto) 
                break

    # --- REPORTE TELEGRAM ---
    clones, opuestos = obtener_espejos(SIMBOLO, 85) # Filtro de Correlación
    tendencia_txt = "ALCISTA 🐂 (Buscando Soportes)" if tendencia_alcista else "BAJISTA 🐻 (Buscando Resistencias)"
    
    reporte = f"""
📊 *REPORTE TENDENCIAL: {SIMBOLO}*
⏱ *Vela:* {timestamp_actual}
---------------------------------------
💰 *Precio:* {vela_actual['close']}
🌊 *Tendencia:* {tendencia_txt}
🧱 *Zonas Activas:* {NUM_ZONAS} Cajas Calculadas
🔗 *Correlación 4H:* Vigilar {list(opuestos.keys())[:2]} (Opuestos)
"""
    if orden_tipo is not None:
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": SIMBOLO, "volume": LOTE,
            "type": orden_tipo, "price": precio_entrada, "sl": sl, "tp": tp,
            "deviation": 20, "magic": 999, "comment": "Trend Pullback",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            reporte += f"\n🚨 *¡PULLBACK DETECTADO!* 🚨\nEl precio rebotó en la caja: {zona_gatillo['centro']:.5f}\n✅ Operación ejecutada.\n🎟 Ticket: {res.order}"
        else:
            reporte += f"\n❌ *Error:* {res.retcode}"
    else:
        if zona_gatillo:
            reporte += f"\n🎯 *Estado:* El precio está DENTRO de la caja {zona_gatillo['centro']:.5f}. Esperando confirmación de rebote..."
        else:
            reporte += "\n🎯 *Estado:* Precio flotando. Esperando retroceso a una zona..."

    return timestamp_actual, reporte

# ==========================================
# 3. EL EVENT LOOP
# ==========================================
if __name__ == "__main__":
    inicializar_mt5()
    enviar_telegram("🚀 *SISTEMA TREND FOLLOWER INICIADO* 🚀\nEstrategia: Pullbacks a Zonas K-Means.")
    ultima_vela_procesada = None
    print("Iniciando Bucle... Presiona Ctrl+C para detener.")

    try:
        while True:
            ahora = datetime.now().strftime("%H:%M:%S")
            velas_temp = mt5.copy_rates_from_pos(SIMBOLO, TEMPORALIDAD, 0, 3)
            
            if velas_temp is not None:
                timestamp_vela_candidata = pd.to_datetime(velas_temp[1]['time'], unit='s')
                
                if ultima_vela_procesada != timestamp_vela_candidata:
                    print(f"\n[{ahora}] Nueva vela. Calculando Zonas y Tendencia...")
                    timestamp_procesado, reporte_texto = analizar_mercado()
                    
                    if timestamp_procesado is not None:
                        enviar_telegram(reporte_texto)
                        ultima_vela_procesada = timestamp_procesado
                        print(f"[{ahora}] Análisis finalizado. Telegram enviado.")
                else:
                    print(f"\r[{ahora}] Escaneando... Esperando cierre de vela de 1H.", end="", flush=True)
            
            time.sleep(60)

    except KeyboardInterrupt:
        enviar_telegram("🛑 *SISTEMA DETENIDO* 🛑")
        mt5.shutdown()
        print("\nApagado manual.")