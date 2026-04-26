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
VELAS_TOTALES = 60000        
VENTANA_ZONAS = 1000         
RECALCULAR_CADA = 24         
NUM_ZONAS = 12
VENTANA_Z_SCORE = 250        
VENTANA_IMPULSO = 40         # Para detectar la pierna A -> B
PULLBACK_ATR_MULT = 1.0

def configurar_carpetas():
    if not os.path.exists("Data_Lake/Monedas"):
        os.makedirs("Data_Lake/Monedas")

def calcular_zonas_historicas(df_slice):
    idx_picos, _ = find_peaks(df_slice['high'], distance=3)
    idx_valles, _ = find_peaks(-df_slice['low'], distance=3)
    
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
    print(f"\n[1/4] Descargando histórico de {simbolo}...")
    if not mt5.initialize():
        print("Error en MT5")
        return

    mt5.symbol_select(simbolo, True)
    datos = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_TOTALES)
    mt5.shutdown()

    if datos is None: return

    df = pd.DataFrame(datos)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print("[2/4] Calculando Z-Score y Momentum (SMA, ADX, ATR)...")
    media_z = df['close'].rolling(window=VENTANA_Z_SCORE).mean()
    std_z = df['close'].rolling(window=VENTANA_Z_SCORE).std()
    df['z_score'] = (df['close'] - media_z) / std_z

    df.ta.sma(length=200, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.atr(length=14, append=True)
    
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Identificación dinámica de columnas
    col_sma200 = [c for c in df.columns if c.startswith('SMA_200')][0]
    col_sma20 = [c for c in df.columns if c.startswith('SMA_20')][0]
    col_adx = [c for c in df.columns if c.startswith('ADX')][0]
    col_dmp = [c for c in df.columns if c.startswith('DMP')][0]
    col_dmn = [c for c in df.columns if c.startswith('DMN')][0]
    col_atr = [c for c in df.columns if c.startswith('ATR')][0]

    # Clasificación Base
    df['tendencia'] = np.where(df['close'] > df[col_sma200], 'ALCISTA', 'BAJISTA')
    df['fuerza_adx'] = np.where(df[col_adx] >= 25, 'FUERTE', 'DEBIL')

    print("[3/4] Recreando lógica de Pullback e Impulsos en el pasado...")
    gatillos = []
    profundidades = []

    # Iteramos para calcular el contexto de cada vela como si estuviera en vivo
    for i in range(len(df)):
        if i < VENTANA_IMPULSO + 3:
            gatillos.append(0)
            profundidades.append(0.0)
            continue
            
        df_impulso = df.iloc[i - VENTANA_IMPULSO : i]
        velas_recientes = df.iloc[i - 3 : i]
        vela_actual = df.iloc[i]
        
        tendencia = vela_actual['tendencia']
        fuerza = vela_actual['fuerza_adx']
        precio = vela_actual['close']
        atr = vela_actual[col_atr]
        zona_pullback_atr = atr * PULLBACK_ATR_MULT
        sma20 = vela_actual[col_sma20]
        
        gatillo = 0
        profundidad = 0.0
        
        if tendencia == "ALCISTA" and fuerza == "FUERTE" and vela_actual[col_dmp] > vela_actual[col_dmn]:
            punto_b = df_impulso['high'].max()
            idx_b = df_impulso['high'].idxmax()
            df_previo = df_impulso.loc[:idx_b]
            punto_a = df_previo['low'].min() if not df_previo.empty else df_impulso['low'].min()
            leg_size = punto_b - punto_a
            
            if leg_size > 0:
                fib_38 = punto_b - (leg_size * 0.382)
                fib_61 = punto_b - (leg_size * 0.618)
                
                toque_sma = any(v['low'] <= (v[col_sma20] + zona_pullback_atr) for _, v in velas_recientes.iterrows())
                en_zona_fib = (fib_61 - zona_pullback_atr) <= vela_actual['low'] <= (fib_38 + zona_pullback_atr)
                
                if toque_sma and en_zona_fib and precio > sma20:
                    gatillo = 1 # COMPRA
                
                profundidad = (punto_b - precio) / atr if atr > 0 else 0.0

        elif tendencia == "BAJISTA" and fuerza == "FUERTE" and vela_actual[col_dmn] > vela_actual[col_dmp]:
            punto_b = df_impulso['low'].min()
            idx_b = df_impulso['low'].idxmin()
            df_previo = df_impulso.loc[:idx_b]
            punto_a = df_previo['high'].max() if not df_previo.empty else df_impulso['high'].max()
            leg_size = punto_a - punto_b
            
            if leg_size > 0:
                fib_38 = punto_b + (leg_size * 0.382)
                fib_61 = punto_b + (leg_size * 0.618)
                
                toque_sma = any(v['high'] >= (v[col_sma20] - zona_pullback_atr) for _, v in velas_recientes.iterrows())
                en_zona_fib = (fib_38 - zona_pullback_atr) <= vela_actual['high'] <= (fib_61 + zona_pullback_atr)
                
                if toque_sma and en_zona_fib and precio < sma20:
                    gatillo = -1 # VENTA
                
                profundidad = (precio - punto_b) / atr if atr > 0 else 0.0

        gatillos.append(gatillo)
        profundidades.append(profundidad)

    df['gatillo_pullback'] = gatillos
    df['profundidad_pullback_atr'] = profundidades

    print("[4/4] Extrayendo Zonas K-Means (Fallback preventivo activado)...")
    # Evitamos NaNs inicializando con un valor alto
    df['distancia_resistencia'] = 999.0
    df['distancia_soporte'] = 999.0
    df['en_zona_kmeans'] = 0

    for i in range(VENTANA_ZONAS, len(df), RECALCULAR_CADA):
        ventana_pasado = df.iloc[i - VENTANA_ZONAS : i]
        zonas_activas = calcular_zonas_historicas(ventana_pasado)
        
        limite_futuro = min(i + RECALCULAR_CADA, len(df))
        
        for j in range(i, limite_futuro):
            precio_actual = df.iloc[j]['close']
            atr_actual = df.iloc[j][col_atr]
            
            resistencias = [z['piso'] for z in zonas_activas if z['piso'] > precio_actual]
            soportes = [z['techo'] for z in zonas_activas if z['techo'] < precio_actual]
            
            d_res = min(resistencias) - precio_actual if resistencias else 999.0
            d_sop = precio_actual - max(soportes) if soportes else 999.0
            
            df.at[j, 'distancia_resistencia'] = d_res
            df.at[j, 'distancia_soporte'] = d_sop
            
            # Etiquetado booleano de zona
            if d_res <= atr_actual * 0.5 or d_sop <= atr_actual * 0.5:
                df.at[j, 'en_zona_kmeans'] = 1

    db_path = f"Data_Lake/Monedas/{simbolo}.db"
    conexion = sqlite3.connect(db_path)
    df.to_sql("historico", conexion, if_exists="replace", index=False)
    conexion.close()
    
    print(f"✅ Extracción finalizada para {simbolo}. Registros: {len(df)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extractor Histórico")
    parser.add_argument("simbolo", type=str, help="El par de divisas a extraer (ej. EURUSD)")
    args = parser.parse_args()
    
    configurar_carpetas()
    extraer_y_procesar(args.simbolo.upper())