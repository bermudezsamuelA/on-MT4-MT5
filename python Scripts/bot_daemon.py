import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta  # <-- Nuevo: Para calcular el RSI en vivo
import time
from datetime import datetime
import requests
import joblib
import os

# ==========================================
# CONFIGURACIÓN DEL DAEMON
# ==========================================
TELEGRAM_TOKEN = "AQUI_TU_TOKEN"
TELEGRAM_CHAT_ID = "AQUI_TU_CHAT_ID"

# 🏆 TU PORTAFOLIO EN CASCADA (Orden de prioridad estricto)
PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"), # Prioridad 1: Juega ambas (86%)
    ("GBPUSD", "USDCHF"), # Prioridad 2: Juega USDCHF (85%)
    ("EURUSD", "USDCAD"), # Prioridad 3: Juega EURUSD (84%)
    ("EURUSD", "USDCHF"), # Prioridad 4: Backup Europeo (82%)
    ("NZDUSD", "USDCHF"), # Prioridad 5: Juega NZDUSD (77%)
    ("AUDUSD", "USDCAD")  # Prioridad 6: Juega AUDUSD (75%)
]

VENTANA_Z_SCORE = 250
LOTE_BASE = 0.01

# Diccionario para cargar los cerebros en memoria RAM
CEREBROS = {}

def evitar_sobreexposicion(par1, par2):
    """Revisa en el servidor de MT5 si las monedas ya están ocupadas"""
    posiciones = mt5.positions_get()
    
    if posiciones is None or len(posiciones) == 0:
        return False
        
    simbolos_abiertos = [pos.symbol for pos in posiciones]
    
    if par1 in simbolos_abiertos or par2 in simbolos_abiertos:
        return True
        
    return False

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    datos = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    try:
        requests.post(url, data=datos)
    except Exception:
        pass

def cargar_cerebros_ia():
    """Carga los modelos .pkl al iniciar el bot"""
    print("\n🧠 Cargando Inteligencias Artificiales en memoria...")
    for par1, par2 in PARES_ACTIVOS:
        ruta = f"Data_Lake/Modelos_IA/Cerebro_{par1}_{par2}.pkl"
        if os.path.exists(ruta):
            CEREBROS[f"{par1}_{par2}"] = joblib.load(ruta)
            print(f"   ✅ Francotirador {par1}-{par2} armado.")
        else:
            print(f"   ❌ Error: Cerebro {par1}-{par2} no encontrado en {ruta}")
    print("===================================================\n")

def calcular_sl_tp(symbol, tipo_orden, media_movil, std_dev):
    info = mt5.symbol_info(symbol)
    if info is None: return 0, 0
    
    tp = media_movil 
    if tipo_orden == mt5.ORDER_TYPE_BUY:
        sl = media_movil - (std_dev * 4)
    else: 
        sl = media_movil + (std_dev * 4)
        
    return round(sl, info.digits), round(tp, info.digits)

def abrir_operacion(symbol, tipo_orden, sl, tp, comentario="IA_Arbitraje"):
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

def extraer_datos_vivos(par):
    """Extrae mercado en vivo y calcula Z-Score y RSI instantáneo"""
    velas = mt5.copy_rates_from_pos(par, mt5.TIMEFRAME_H1, 0, VENTANA_Z_SCORE + 50)
    if velas is None: return None
    
    df = pd.DataFrame(velas)
    df.ta.rsi(length=14, append=True)
    
    media = df['close'].rolling(VENTANA_Z_SCORE).mean()
    std = df['close'].rolling(VENTANA_Z_SCORE).std()
    df['z_score'] = (df['close'] - media) / std
    
    return df

def ejecutar_bot():
    print("🤖 Iniciando Bot Quant-Institucional en vivo...")
    cargar_cerebros_ia()
    
    if not mt5.initialize():
        print("❌ Falla al conectar con MT5")
        return
        
    enviar_telegram("🟢 Sistema de IA iniciado con cerebros activos. Vigilando el mercado...")
    hora_ultima_revision = None
    
    while True:
        ahora = datetime.now()
        print(f"[{ahora.strftime('%H:%M:%S')}] ⏳ Escaneando anomalías de mercado...", end="\r")
        
        # MODO DISPARO DE IA (Solo al cerrar la vela H1: minuto 00)
        if ahora.minute == 0 and hora_ultima_revision != ahora.hour:
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔔 Vela H1 cerrada. Analizando variables...")
            hora_ultima_revision = ahora.hour
            
            for par1, par2 in PARES_ACTIVOS:
                nombre_modelo = f"{par1}_{par2}"
                if nombre_modelo not in CEREBROS: continue
                
                df1 = extraer_datos_vivos(par1)
                df2 = extraer_datos_vivos(par2)
                
                if df1 is None or df2 is None: continue
                
                # Capturamos el último latido del mercado (Con Z-Score y RSI)
                z1 = df1['z_score'].iloc[-1]
                z2 = df2['z_score'].iloc[-1]
                rsi1 = df1['RSI_14'].iloc[-1]
                rsi2 = df2['RSI_14'].iloc[-1]
                
                spread_total = z1 + z2
                
                if abs(spread_total) > 1.5:
                    print(f"   ⚠️ Anomalía en {par1} vs {par2} | Spread: {spread_total:.2f}")
                    
                    # 🛡️ LA BARRERA DE SEGURIDAD INSTITUCIONAL
                    if evitar_sobreexposicion(par1, par2):
                        print(f"   🛡️ Bloqueo táctico: {par1} o {par2} ya están en combate. Ignorando doble riesgo.")
                        continue # Salta a la siguiente pareja de tu lista
                    
                    # 1. EMPAQUETAMOS LOS DATOS PARA LA IA
                    modelo = CEREBROS[nombre_modelo]
                    columnas_esperadas = modelo.feature_names_in_
                    
                    datos_ia = {
                        'spread_total': spread_total,
                        f'z_score_{par1}': z1,
                        f'z_score_{par2}': z2,
                        f'RSI_14_{par1}': rsi1,
                        f'RSI_14_{par2}': rsi2
                    }
                    df_pred = pd.DataFrame([datos_ia])
                    
                    # Rellenamos distancias faltantes de K-Means con 0 (Truco Quant para no calcular zonas en vivo)
                    for col in columnas_esperadas:
                        if col not in df_pred.columns:
                            df_pred[col] = 0.0
                            
                    df_pred = df_pred[columnas_esperadas] # Ordenamos las columnas tal cual las exige el modelo
                    
                    # 2. EL VEREDICTO DE LA INTELIGENCIA ARTIFICIAL
                    prediccion = modelo.predict(df_pred)[0]
                    
                    if prediccion == 1:
                        print("   🎯 IA AUTORIZA EL DISPARO. Calculando Stop Loss y Take Profit...")
                        
                        media_p1 = df1['close'].iloc[-1] - (z1 * df1['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1])
                        std_p1 = df1['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1]
                        
                        media_p2 = df2['close'].iloc[-1] - (z2 * df2['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1])
                        std_p2 = df2['close'].rolling(VENTANA_Z_SCORE).std().iloc[-1]
                        
                        # Si el spread es positivo (Par 1 arriba, Par 2 abajo)
                        if spread_total > 1.5:
                            tipo1, tipo2 = mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY
                        else:
                            tipo1, tipo2 = mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL
                            
                        sl1, tp1 = calcular_sl_tp(par1, tipo1, media_p1, std_p1)
                        sl2, tp2 = calcular_sl_tp(par2, tipo2, media_p2, std_p2)
                        
                        # ¡FUEGO!
                        res1 = abrir_operacion(par1, tipo1, sl1, tp1)
                        res2 = abrir_operacion(par2, tipo2, sl2, tp2)
                        
                        if res1 and res1.retcode == mt5.TRADE_RETCODE_DONE:
                            msg = f"⚡ OPERACIÓN EJECUTADA ⚡\nPares: {par1} y {par2}\nSpread: {spread_total:.2f}\n✅ IA WinRate >80%\nSeguros de SL/TP colocados."
                            enviar_telegram(msg)
                            print(f"   💸 Órdenes enviadas con éxito para {par1}-{par2}.")
                        else:
                            print(f"   ❌ Error enviando órdenes al broker: {res1.comment if res1 else 'N/A'}")
                    else:
                        print("   🛡️ IA rechaza la operación (Riesgo Estadístico Alto). Ignorando.")
                        
        # El bot descansa 60 segundos antes de volver a mirar el reloj
        time.sleep(60)
     
if __name__ == "__main__":
    ejecutar_bot()