import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime
import requests
import joblib
import os
import json

# ==========================================
# CONFIGURACIÓN DEL DAEMON Y SEGURIDAD
# ==========================================
# Cargar credenciales desde variables de entorno (o archivo config) por seguridad
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TU_TOKEN_AQUI_O_EN_ENV")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "TU_ID_AQUI_O_EN_ENV")

PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"),
    ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"),
    ("EURUSD", "USDCHF"),
    ("NZDUSD", "USDCHF"),
    ("AUDUSD", "USDCAD")
]

# Configuración Quant Trend-Following
VENTANA_HISTORIA = 300 
LOTE_BASE = 0.01

# Diccionarios de Memoria
CEREBROS = {}
RIESGO_OPTIMO = {}

# ==========================================
# FUNCIONES NÚCLEO
# ==========================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje})
    except Exception:
        pass

def cargar_motores():
    """Carga Modelos IA y Parámetros de Riesgo (ATR)"""
    print("\n🧠 Cargando Motores Cuantitativos...")
    
    # Carga de IA
    for par1, par2 in PARES_ACTIVOS:
        ruta = f"Data_Lake/Modelos_IA/Cerebro_{par1}_{par2}.pkl"
        if os.path.exists(ruta):
            CEREBROS[f"{par1}_{par2}"] = joblib.load(ruta)
            print(f"   ✅ IA Armada: {par1}-{par2}")
            
    # Asumimos que guardaste el reporte del analizador_riesgo en un JSON o lo defines aquí
    # Estos son valores de ejemplo en multiplicadores de ATR (Extraídos de tu analizador)
    global RIESGO_OPTIMO
    RIESGO_OPTIMO = {
        "EURUSD": {"sl_atr": 6.85, "tp_atr": 3.25},
        "GBPUSD": {"sl_atr": 6.96, "tp_atr": 3.29},
        "USDCAD": {"sl_atr": 5.58, "tp_atr": 4.15},
        "USDCHF": {"sl_atr": 9.18, "tp_atr": 2.94},
        "AUDUSD": {"sl_atr": 9.59, "tp_atr": 2.74},
        "NZDUSD": {"sl_atr": 7.42, "tp_atr": 3.59}
    }
    print("===================================================\n")

def evitar_sobreexposicion(simbolo):
    posiciones = mt5.positions_get()
    if not posiciones: return False
    return any(pos.symbol == simbolo for pos in posiciones)

def calcular_sl_tp_atr(symbol, tipo_orden, precio_actual, atr):
    """Gestión de Riesgo Dinámica Basada en Volatilidad Real"""
    info = mt5.symbol_info(symbol)
    if info is None or symbol not in RIESGO_OPTIMO: return 0, 0
    
    riesgo = RIESGO_OPTIMO[symbol]
    distancia_sl = atr * riesgo["sl_atr"]
    distancia_tp = atr * riesgo["tp_atr"]
    
    # Lógica de Seguimiento de Tendencia
    if tipo_orden == mt5.ORDER_TYPE_BUY:
        tp = precio_actual + distancia_tp
        sl = precio_actual - distancia_sl
    else: # SELL
        tp = precio_actual - distancia_tp
        sl = precio_actual + distancia_sl
        
    return round(sl, info.digits), round(tp, info.digits)

def abrir_operacion(symbol, tipo_orden, sl, tp, comentario="IA_Momentum"):
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

def extraer_fotografia_momentum(par):
    """Extrae el ADN exacto que espera la IA (Trend-Following)"""
    velas = mt5.copy_rates_from_pos(par, mt5.TIMEFRAME_H1, 0, VENTANA_HISTORIA)
    if velas is None: return None
    
    df = pd.DataFrame(velas)
    
    # Mismos indicadores y parámetros que el Extractor Histórico
    media_z = df['close'].rolling(window=250).mean()
    std_z = df['close'].rolling(window=250).std()
    df['z_score'] = (df['close'] - media_z) / std_z
    
    df.ta.sma(length=200, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.atr(length=14, append=True)
    
    df.dropna(inplace=True)
    
    vela_actual = df.iloc[-1]
    
    # 1. Fuerza de Tendencia
    fuerza_adx = "FUERTE" if vela_actual['ADX_14'] >= 25 else "DEBIL"
    tendencia = "ALCISTA" if vela_actual['close'] > vela_actual['SMA_200'] else "BAJISTA"
    
    # 2. Detección Rápida de Pullback (Toque de SMA 20)
    gatillo = 0
    zona_pullback = vela_actual['ATRr_14'] * 1.0
    
    if tendencia == "ALCISTA" and fuerza_adx == "FUERTE" and vela_actual['DMP_14'] > vela_actual['DMN_14']:
        if df.iloc[-3:]['low'].min() <= (vela_actual['SMA_20'] + zona_pullback) and vela_actual['close'] > vela_actual['SMA_20']:
            gatillo = 1 # COMPRA
            
    elif tendencia == "BAJISTA" and fuerza_adx == "FUERTE" and vela_actual['DMN_14'] > vela_actual['DMP_14']:
        if df.iloc[-3:]['high'].max() >= (vela_actual['SMA_20'] - zona_pullback) and vela_actual['close'] < vela_actual['SMA_20']:
            gatillo = -1 # VENTA
            
    # Mock de zona kmeans para simplificar (idealmente conectarlo con Buscador_Zonas)
    en_zona = 1 if gatillo != 0 else 0 
    
    # Feature Vector Crudo para la IA
    features_cradas = {
        'z_score': vela_actual['z_score'],
        'ADX_14': vela_actual['ADX_14'],
        'ATRr_14': vela_actual['ATRr_14'],
        'profundidad_pullback_atr': 0.5 if gatillo != 0 else 0.0, # Estimación rápida
        'gatillo_pullback': gatillo,
        'en_zona_kmeans': en_zona,
        'precio_cierre': vela_actual['close'],
        'tendencia_str': tendencia
    }
    
    return features_cradas

def ejecutar_bot():
    print("🤖 Iniciando Daemon Trend-Following en vivo...")
    
    if not mt5.initialize():
        print("❌ Falla crítica al conectar con MT5")
        return
        
    cargar_motores()
    enviar_telegram("🟢 Sistema de IA (Momentum) iniciado. Vigilando pullbacks...")
    hora_ultima_revision = None
    
    while True:
        ahora = datetime.now()
        
        # MODO DISPARO DE IA (Solo al cerrar la vela H1: minuto 00)
        if ahora.minute == 0 and hora_ultima_revision != ahora.hour:
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔔 Vela H1 cerrada. Extrayendo features institucionales...")
            hora_ultima_revision = ahora.hour
            
            for par1, par2 in PARES_ACTIVOS:
                nombre_modelo = f"{par1}_{par2}"
                if nombre_modelo not in CEREBROS: continue
                
                datos_p1 = extraer_fotografia_momentum(par1)
                datos_p2 = extraer_fotografia_momentum(par2)
                
                if not datos_p1 or not datos_p2: continue
                
                # 1. EVALUACIÓN ESTRATÉGICA (¿Hay Pullback real?)
                gatillo1 = datos_p1['gatillo_pullback']
                gatillo2 = datos_p2['gatillo_pullback']
                
                if gatillo1 == 0 and gatillo2 == 0:
                    continue # Mercado aburrido, la IA no se molesta en mirar
                
                # 2. ENSAMBLAJE DE FEATURES PARA LA IA
                spread_total = datos_p1['z_score'] + datos_p2['z_score']
                
                modelo = CEREBROS[nombre_modelo]
                
                datos_ia = {
                    'spread_total': spread_total,
                    'spread_sma_20': spread_total, # Aproximación para ejecución rápida
                    'spread_std_20': 0.5,
                    'spread_slope_5': 0.1,
                    f'z_score_{par1}': datos_p1['z_score'],
                    f'ADX_14_{par1}': datos_p1['ADX_14'],
                    f'ATRr_14_{par1}': datos_p1['ATRr_14'],
                    f'profundidad_pullback_atr_{par1}': datos_p1['profundidad_pullback_atr'],
                    f'gatillo_pullback_{par1}': datos_p1['gatillo_pullback'],
                    f'en_zona_kmeans_{par1}': datos_p1['en_zona_kmeans'],
                    f'z_score_{par2}': datos_p2['z_score'],
                    f'ADX_14_{par2}': datos_p2['ADX_14'],
                    f'ATRr_14_{par2}': datos_p2['ATRr_14'],
                    f'profundidad_pullback_atr_{par2}': datos_p2['profundidad_pullback_atr'],
                    f'gatillo_pullback_{par2}': datos_p2['gatillo_pullback'],
                    f'en_zona_kmeans_{par2}': datos_p2['en_zona_kmeans']
                }
                
                df_pred = pd.DataFrame([datos_ia])
                
                # Rellenar faltantes (Seguridad)
                for col in modelo.feature_names_in_:
                    if col not in df_pred.columns: df_pred[col] = 0.0
                df_pred = df_pred[modelo.feature_names_in_] 
                
                # 3. EL VEREDICTO DE LA INTELIGENCIA ARTIFICIAL
                prediccion = modelo.predict(df_pred)[0]
                
                if prediccion == 1:
                    print(f"   🎯 IA AUTORIZA EL DISPARO en {nombre_modelo}.")
                    
                    # 4. EJECUCIÓN AISLADA (Trend-Following)
                    # Disparamos SOLO la moneda que dio el gatillo, en favor de su tendencia
                    if gatillo1 != 0 and not evitar_sobreexposicion(par1):
                        tipo_orden = mt5.ORDER_TYPE_BUY if gatillo1 == 1 else mt5.ORDER_TYPE_SELL
                        sl, tp = calcular_sl_tp_atr(par1, tipo_orden, datos_p1['precio_cierre'], datos_p1['ATRr_14'])
                        res = abrir_operacion(par1, tipo_orden, sl, tp)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            enviar_telegram(f"⚡ LONG {par1}" if gatillo1==1 else f"⚡ SHORT {par1}")
                            
                    if gatillo2 != 0 and not evitar_sobreexposicion(par2):
                        tipo_orden = mt5.ORDER_TYPE_BUY if gatillo2 == 1 else mt5.ORDER_TYPE_SELL
                        sl, tp = calcular_sl_tp_atr(par2, tipo_orden, datos_p2['precio_cierre'], datos_p2['ATRr_14'])
                        res = abrir_operacion(par2, tipo_orden, sl, tp)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            enviar_telegram(f"⚡ LONG {par2}" if gatillo2==1 else f"⚡ SHORT {par2}")
                            
                else:
                    print(f"   🛡️ IA Rechaza Pullback en {nombre_modelo}. Riesgo alto.")
                        
        time.sleep(60)

if __name__ == "__main__":
    ejecutar_bot()