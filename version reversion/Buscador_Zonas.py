import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import KMeans
from pares_arbitraje import MONEDAS_ACTIVAS # Importamos tu lista dinámica

# ==========================================
# CONFIGURACIÓN DEL RADAR
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H4  
VELAS_HISTORIAL = 1000           
NUM_ZONAS = 12                   
DISTANCIA_PICOS = 3 

def obtener_zonas_mercado():
    """
    Escanea todas las monedas activas y devuelve un diccionario con sus zonas de reacción.
    Formato de salida: {'EURUSD': [{'piso': x, 'techo': y}, ...], 'USDCHF': [...]}
    """
    if not mt5.initialize():
        print("Error al inicializar MT5")
        return None

    mega_diccionario_zonas = {}

    print(f"📡 Iniciando escaneo de Zonas Institucionales para {len(MONEDAS_ACTIVAS)} monedas...")

    for simbolo in MONEDAS_ACTIVAS:
        # 1. Extracción
        mt5.symbol_select(simbolo, True)
        velas = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_HISTORIAL)
        
        if velas is None:
            print(f"⚠️ No se pudieron obtener datos para {simbolo}")
            continue

        df = pd.DataFrame(velas)
        
        # 2. Detección de Fractales
        idx_picos, _ = find_peaks(df['high'], distance=DISTANCIA_PICOS)
        idx_valles, _ = find_peaks(-df['low'], distance=DISTANCIA_PICOS)
        rebotes = np.concatenate((df['high'].iloc[idx_picos].values, df['low'].iloc[idx_valles].values))
        matriz_rebotes = rebotes.reshape(-1, 1)

        # 3. K-Means (Cajas Rojas)
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
        
        print(f"✅ {simbolo}: {NUM_ZONAS} Zonas calculadas.")

    mt5.shutdown()
    print("🎯 Escaneo multimoneda finalizado.\n")
    return mega_diccionario_zonas

# Si ejecutas este archivo solo, hará un test rápido:
if __name__ == "__main__":
    zonas = obtener_zonas_mercado()
    if zonas:
        print("Muestra de la primera zona del EURUSD:")
        print(zonas.get("EURUSD", [])[0])