import MetaTrader5 as mt5
import pandas as pd
import time
import requests
from datetime import datetime
from pares_arbitraje import analizar_anomalias_arbitraje # Importamos tu cerebro

# ==========================================
# 1. PANEL DE CONTROL
# ==========================================
TOKEN = "8668581533:AAHjwwdTZ6Tylq8_w8dz-MqGySPUlIhyb3k"
CHAT_ID = "1133179366"
TEMPORALIDAD = mt5.TIMEFRAME_H1 

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except:
        pass

# ==========================================
# 2. EL EVENT LOOP (Vigilante 24/5)
# ==========================================
def iniciar_daemon():
    if not mt5.initialize():
        print("Error al inicializar MT5")
        return

    enviar_telegram("🚀 *SISTEMA QUANT INICIADO* 🚀\nMonitoreando Trifectas y Arbitraje de Pares...")
    print("Iniciando Bucle de Eventos. Presiona Ctrl+C para detener.")
    
    ultima_vela_procesada = None

    try:
        while True:
            ahora = datetime.now().strftime("%H:%M:%S")
            # Usamos EURUSD solo como "reloj" para saber si la vela de 1H ya cerró
            velas_temp = mt5.copy_rates_from_pos("EURUSD", TEMPORALIDAD, 0, 3)
            
            if velas_temp is not None:
                timestamp_vela_candidata = pd.to_datetime(velas_temp[1]['time'], unit='s')
                
                if ultima_vela_procesada != timestamp_vela_candidata:
                    print(f"\n[{ahora}] 🕒 Cierre de vela detectado. Ejecutando escaneo profundo...")
                    
                    # Llamamos al Cerebro Central
                    resultados = analizar_anomalias_arbitraje(temporalidad=TEMPORALIDAD)
                    
                    # Filtramos solo las alertas importantes
                    alertas_importantes = [r for r in resultados if r['icono'] in ['💎', '🔥', '⚡', '🚨']]
                    
                    if alertas_importantes:
                        mensaje_tg = f"📊 *ESCANEO COMPLETADO: {timestamp_vela_candidata}*\n"
                        mensaje_tg += "---------------------------------------\n"
                        
                        for r in alertas_importantes:
                            mensaje_tg += f"{r['icono']} *{r['par1']} vs {r['par2']}*\n"
                            mensaje_tg += f"Sp: {r['spread']:.2f} | Z1: {r['z1']:.1f} | Z2: {r['z2']:.1f}\n"
                            mensaje_tg += f"_{r['confirmacion']}_\n\n"
                            
                        enviar_telegram(mensaje_tg)
                        print(f"[{ahora}] ¡Alertas encontradas! Telegram enviado.")
                    else:
                        print(f"[{ahora}] Mercado aburrido. Sin alertas estructurales.")

                    ultima_vela_procesada = timestamp_vela_candidata
                else:
                    print(f"\r[{ahora}] Vigilando mercado... Esperando próximo cierre de vela.", end="", flush=True)
            
            time.sleep(60) # Duerme 1 minuto para no saturar el CPU

    except KeyboardInterrupt:
        enviar_telegram("🛑 *SISTEMA DETENIDO* 🛑\nApagado manual del servidor.")
        mt5.shutdown()
        print("\nBot apagado correctamente.")

if __name__ == "__main__":
    iniciar_daemon()