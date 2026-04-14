import MetaTrader5 as mt5
import pandas as pd

# 1. Inicializar la conexión con el terminal de MT5
if not mt5.initialize():
    print("Error al inicializar MT5, código:", mt5.last_error())
    quit()

print("¡Conexión exitosa a MetaTrader 5!")

# 2. Definir los parámetros de extracción
simbolo = "EURUSD"
temporalidad = mt5.TIMEFRAME_H1
cantidad_velas = 10

# 3. Extraer los datos (directo a la memoria de Python)
# copy_rates_from_pos extrae desde la vela actual (posición 0) hacia atrás
velas = mt5.copy_rates_from_pos(simbolo, temporalidad, 0, cantidad_velas)

if velas is None:
    print(f"No se pudieron extraer datos de {simbolo}")
else:
    # 4. Convertir los datos crudos a un DataFrame de Pandas para análisis
    df = pd.DataFrame(velas)
    
    # Convertir el tiempo (que viene en segundos de UNIX) a fecha legible
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"\nÚltimas {cantidad_velas} velas de {simbolo}:")
    print(df[['time', 'open', 'high', 'low', 'close', 'tick_volume']])

# 5. Cerrar la conexión
mt5.shutdown()