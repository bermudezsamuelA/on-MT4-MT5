import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import sqlite3
import os
import argparse
from scipy.signal import find_peaks
from sklearn.cluster import KMeans

# ==========================================
# 1. CONFIGURACIÓN DEL EXTRACTOR
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H1
VELAS_TOTALES = 60000        # Aprox. 10 años de historia en H1
VENTANA_ZONAS = 1000         # Cuánto pasado mira para calcular las zonas
RECALCULAR_CADA = 24         # Recalcula las cajas rojas cada 24 horas (1 día) para optimizar
NUM_ZONAS = 12

def configurar_carpetas():
    if not os.path.exists("Data_Lake/Monedas"):
        os.makedirs("Data_Lake/Monedas")
    print("📁 Estructura de carpetas Data_Lake verificada.")

def calcular_zonas_historicas(df_slice):
    """Calcula K-Means para una ventana de tiempo específica."""
    idx_picos, _ = find_peaks(df_slice['high'], distance=3)
    idx_valles, _ = find_peaks(-df_slice['low'], distance=3)
    
    # Si hay muy pocos rebotes (mercado raro), saltamos
    if len(idx_picos) < NUM_ZONAS or len(idx_valles) < NUM_ZONAS:
        return []

    rebotes = np.concatenate((df_slice['high'].iloc[idx_picos].values, df_slice['low'].iloc[idx_valles].values))
    matriz = rebotes.reshape(-1, 1)

    kmeans = KMeans(n_clusters=NUM_ZONAS, random_state=42, n_init=10).fit(matriz)
    etiquetas = kmeans.labels_
    
    zonas = []
    for i in range(NUM_ZONAS):
        precios = matriz[etiquetas == i].flatten()
        centro = kmeans.cluster_centers_[i][0]
        desviacion = np.std(precios)
        zonas.append({"piso": centro - desviacion, "techo": centro + desviacion})
    return zonas

def extraer_y_procesar(simbolo):
    print(f"\n⏳ Conectando a MT5 para extraer {simbolo}...")
    if not mt5.initialize():
        print("Error MT5")
        return

    mt5.symbol_select(simbolo, True)
    datos = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_TOTALES)
    mt5.shutdown()

    if datos is None:
        print(f"❌ Error al descargar datos de {simbolo}")
        return

    df = pd.DataFrame(datos)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print("🧮 Calculando indicadores técnicos (RSI, Bollinger, SMA)...")
    df.ta.sma(length=200, append=True)
    df.ta.bbands(length=20, std=2.0, append=True)
    df.ta.rsi(length=14, append=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    print("🕰️ Viajando en el tiempo para calcular Zonas K-Means (Esto tomará un minuto)...")
    
    # Nuevas columnas para Machine Learning
    df['distancia_resistencia'] = np.nan
    df['distancia_soporte'] = np.nan

    # Bucle del Tiempo: Avanzamos día a día (cada 24 velas)
    for i in range(VENTANA_ZONAS, len(df), RECALCULAR_CADA):
        # La "foto" del pasado que el bot veía en ese momento exacto
        ventana_pasado = df.iloc[i - VENTANA_ZONAS : i]
        zonas_activas = calcular_zonas_historicas(ventana_pasado)
        
        # Aplicamos esas zonas a las siguientes 24 horas
        limite_futuro = min(i + RECALCULAR_CADA, len(df))
        
        for j in range(i, limite_futuro):
            precio_actual = df.iloc[j]['close']
            resistencias = [z['piso'] for z in zonas_activas if z['piso'] > precio_actual]
            soportes = [z['techo'] for z in zonas_activas if z['techo'] < precio_actual]
            
            # Distancia en puntos puros respecto al precio actual
            if resistencias:
                df.at[j, 'distancia_resistencia'] = min(resistencias) - precio_actual
            if soportes:
                df.at[j, 'distancia_soporte'] = precio_actual - max(soportes)
                
        # Barra de progreso simple
        if i % (RECALCULAR_CADA * 100) == 0:
            progreso = (i / len(df)) * 100
            print(f"   -> Procesando: {progreso:.1f}%")

    print("🧹 Limpiando datos nulos iniciales...")
    df.dropna(inplace=True)

    print("💾 Guardando en Data Lake (SQLite)...")
    db_path = f"Data_Lake/Monedas/{simbolo}.db"
    conexion = sqlite3.connect(db_path)
    # Guardamos el DataFrame entero en SQL en 1 sola línea
    df.to_sql("historico", conexion, if_exists="replace", index=False)
    conexion.close()
    
    print(f"✅ ¡Éxito! Base de datos {simbolo}.db creada con {len(df)} filas listas para Machine Learning.")

if __name__ == "__main__":
    # Permite ejecutar el script pasándole la moneda por consola
    parser = argparse.ArgumentParser(description="Extractor Histórico para Data Lake")
    parser.add_argument("simbolo", type=str, help="El par de divisas a extraer (ej. EURUSD)")
    args = parser.parse_args()
    
    configurar_carpetas()
    extraer_y_procesar(args.simbolo.upper())