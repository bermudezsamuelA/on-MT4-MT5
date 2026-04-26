import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import KMeans
from pares_arbitraje import MONEDAS_ACTIVAS 

# ==========================================
# CONFIGURACIÓN DEL RADAR (Alineado al Extractor)
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H1  # ⚡ Obligatorio: Mismo marco temporal que el dataset ML
VELAS_HISTORIAL = 1000           
NUM_ZONAS = 12                   
DISTANCIA_PICOS = 3 

def obtener_zonas_mercado():
    """
    Escanea todas las monedas activas y devuelve un diccionario con sus zonas de reacción.
    Calcula exactamente en el mismo marco de tiempo (H1) que el Extractor Histórico.
    """
    mega_diccionario_zonas = {}

    print(f"📡 Iniciando escaneo de Zonas Institucionales H1 para {len(MONEDAS_ACTIVAS)} monedas...")

    for simbolo in MONEDAS_ACTIVAS:
        # 1. Extracción (Sin initialize/shutdown aquí adentro)
        mt5.symbol_select(simbolo, True)
        velas = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_HISTORIAL)
        
        if velas is None:
            print(f"   ⚠️ No se pudieron obtener datos para {simbolo}")
            continue

        df = pd.DataFrame(velas)
        
        # 2. Detección de Fractales
        idx_picos, _ = find_peaks(df['high'], distance=DISTANCIA_PICOS)
        idx_valles, _ = find_peaks(-df['low'], distance=DISTANCIA_PICOS)
        
        # Fallback preventivo: Si el mercado no tiene estructura, lo saltamos
        if len(idx_picos) < NUM_ZONAS or len(idx_valles) < NUM_ZONAS:
            print(f"   ⚠️ {simbolo}: Muy pocos fractales detectados. Omitiendo zonas.")
            mega_diccionario_zonas[simbolo] = []
            continue
            
        rebotes = np.concatenate((df['high'].iloc[idx_picos].values, df['low'].iloc[idx_valles].values))
        matriz_rebotes = rebotes.reshape(-1, 1)

        # 3. K-Means (Cajas de reacción)
        kmeans = KMeans(n_clusters=NUM_ZONAS, random_state=42, n_init=10).fit(matriz_rebotes)
        etiquetas = kmeans.labels_
        
        zonas_simbolo = []
        for i in range(NUM_ZONAS):
            precios = matriz_rebotes[etiquetas == i].flatten()
            centroide = kmeans.cluster_centers_[i][0]
            desviacion = np.std(precios)
            
            zonas_simbolo.append({
                "piso": centroide - desviacion,
                "techo": centroide + desviacion,
                "centro": centroide
            })

        # Ordenar de mayor a menor precio
        zonas_simbolo = sorted(zonas_simbolo, key=lambda x: x['centro'], reverse=True)
        mega_diccionario_zonas[simbolo] = zonas_simbolo
        
        print(f"   ✅ {simbolo}: {NUM_ZONAS} Zonas calculadas en H1.")

    print("🎯 Escaneo de Zonas finalizado.\n")
    return mega_diccionario_zonas

# Zona de pruebas aislada
if __name__ == "__main__":
    if mt5.initialize():
        zonas = obtener_zonas_mercado()
        if zonas:
            print("\nMuestra de la primera zona del EURUSD:")
            print(zonas.get("EURUSD", [])[0] if "EURUSD" in zonas and zonas["EURUSD"] else "Sin zonas.")
        mt5.shutdown()