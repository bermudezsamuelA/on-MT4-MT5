import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from sklearn.cluster import KMeans

# ==========================================
# 1. CONFIGURACIÓN DEL BUSCADOR
# ==========================================
SIMBOLO = "EURUSD"
TEMPORALIDAD = mt5.TIMEFRAME_H4  # H4 es ideal para buscar zonas institucionales fuertes
VELAS_HISTORIAL = 1000           # Cuanta más historia, más precisas las zonas
NUM_ZONAS = 12                    # Cuántas "Cajas Rojas" (Clusters) queremos encontrar
DISTANCIA_PICOS = 3              # Cuántas velas de separación mínima entre un rebote y otro

# ==========================================
# 2. CONEXIÓN Y EXTRACCIÓN
# ==========================================
if not mt5.initialize():
    print("Error al inicializar MT5")
    quit()

print(f"📡 Descargando historial profundo de {SIMBOLO}...")
velas = mt5.copy_rates_from_pos(SIMBOLO, TEMPORALIDAD, 0, VELAS_HISTORIAL)
df = pd.DataFrame(velas)
mt5.shutdown()

if df.empty:
    print("Error: No se pudieron obtener los datos.")
    quit()

# ==========================================
# 3. DETECCIÓN DE REBOTES (FRACTALES)
# ==========================================
print("🔍 Buscando rebotes históricos (picos y valles)...")

# Buscamos los picos (Resistencias / Techos)
# distance=DISTANCIA_PICOS asegura que no tome pequeños ruidos en la misma vela
indices_picos, _ = find_peaks(df['high'], distance=DISTANCIA_PICOS)
precios_picos = df['high'].iloc[indices_picos].values

# Buscamos los valles (Soportes / Pisos)
# Invertimos el array multiplicando por -1 para que la fórmula encuentre los mínimos
indices_valles, _ = find_peaks(-df['low'], distance=DISTANCIA_PICOS)
precios_valles = df['low'].iloc[indices_valles].values

# Unimos todos los rebotes en una sola lista para el algoritmo
todos_los_rebotes = np.concatenate((precios_picos, precios_valles))

# Le damos la forma de matriz que exige scikit-learn (1 columna, N filas)
matriz_rebotes = todos_los_rebotes.reshape(-1, 1)

print(f"✅ Se encontraron {len(todos_los_rebotes)} puntos de rebote en las últimas {VELAS_HISTORIAL} velas.")

# ==========================================
# 4. AGRUPAMIENTO K-MEANS (Creación de las Cajas Rojas)
# ==========================================
print("🤖 Ejecutando algoritmo de Machine Learning (K-Means)...")

kmeans = KMeans(n_clusters=NUM_ZONAS, random_state=42, n_init=10)
kmeans.fit(matriz_rebotes)
etiquetas = kmeans.labels_

zonas_de_reaccion = []

for i in range(NUM_ZONAS):
    precios_del_grupo = matriz_rebotes[etiquetas == i].flatten()
    
    # EL TRUCO ESTADÍSTICO PARA ADELGAZAR LAS CAJAS
    # En lugar de tomar el pico más alto (que podría ser una anomalía), 
    # calculamos la Desviación Estándar para descartar el ruido.
    centroide = kmeans.cluster_centers_[i][0]
    desviacion = np.std(precios_del_grupo)
    
    # La caja ahora solo abarcará el "corazón" del volumen de rebotes
    techo_caja = centroide + desviacion
    piso_caja = centroide - desviacion
    cantidad_toques = len(precios_del_grupo)
    
    zonas_de_reaccion.append({
        "piso": piso_caja,
        "techo": techo_caja,
        "centro": centroide,
        "toques": cantidad_toques
    })

zonas_de_reaccion = sorted(zonas_de_reaccion, key=lambda x: x['centro'], reverse=True)

# ==========================================
# 5. REPORTE DE ZONAS INSTITUCIONALES
# ==========================================
print("\n=======================================================")
print(f" 🧱 ZONAS DE REACCIÓN ENCONTRADAS ({SIMBOLO} - H4)")
print("=======================================================")

for idx, zona in enumerate(zonas_de_reaccion):
    grosor_pips = (zona['techo'] - zona['piso']) * 10000 # Convertir la diferencia a pips estándar
    
    print(f"ZONA {idx + 1}:")
    print(f"  🔻 Techo : {zona['techo']:.5f}")
    print(f"  🎯 Centro: {zona['centro']:.5f} (Punto de máxima atracción)")
    print(f"  🔺 Piso  : {zona['piso']:.5f}")
    print(f"  📊 Toques Históricos: {zona['toques']} rebotes")
    print(f"  📏 Grosor de la caja: {grosor_pips:.1f} pips")
    print("-------------------------------------------------------")

print("\n🚀 Cajas Rojas calculadas con éxito.")