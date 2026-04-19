import sqlite3
import pandas as pd
import os

# ==========================================
# CONFIGURACIÓN DEL PIPELINE
# ==========================================
PAR_1 = "EURUSD"
PAR_2 = "USDCHF"
VENTANA_Z_SCORE = 250 # La misma que usa tu bot en vivo

def fusionar_bases_de_datos(par1, par2):
    print(f"🔄 Iniciando Pipeline de Fusión: {par1} vs {par2}")
    
    # 1. Conectar y leer las bases de datos individuales
    try:
        conn1 = sqlite3.connect(f"Data_Lake/Monedas/{par1}.db")
        df1 = pd.read_sql_query("SELECT * FROM historico", conn1)
        conn1.close()
        
        conn2 = sqlite3.connect(f"Data_Lake/Monedas/{par2}.db")
        df2 = pd.read_sql_query("SELECT * FROM historico", conn2)
        conn2.close()
    except Exception as e:
        print(f"❌ Error al leer las bases de datos: {e}")
        return

    # 2. Renombrar columnas para evitar choques antes de unir
    # Dejamos 'time' intacto porque será nuestra llave de unión
    df1.columns = [f"{col}_{par1}" if col != 'time' else 'time' for col in df1.columns]
    df2.columns = [f"{col}_{par2}" if col != 'time' else 'time' for col in df2.columns]

    # 3. El "Inner Join": Unimos ambas tablas exactamente en la misma hora
    print("🧬 Alineando temporalidades (Inner Join)...")
    df_fusion = pd.merge(df1, df2, on='time', how='inner')
    
    # Ordenamos cronológicamente para evitar desastres
    df_fusion.sort_values(by='time', inplace=True)
    df_fusion.reset_index(drop=True, inplace=True)

    # 4. Cálculo Histórico del Spread (Evitando Data Leakage con Ventanas Móviles)
    print(f"📈 Calculando Z-Scores Históricos y Spread (Ventana: {VENTANA_Z_SCORE})...")
    
    # Para el Z-Score calculamos el promedio y std de las ÚLTIMAS 250 velas
    media_p1 = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).mean()
    std_p1 = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion[f'z_score_{par1}'] = (df_fusion[f'close_{par1}'] - media_p1) / std_p1

    media_p2 = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).mean()
    std_p2 = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion[f'z_score_{par2}'] = (df_fusion[f'close_{par2}'] - media_p2) / std_p2

    # El Spread es la suma de los Z-Scores (por ser pares inversos)
    df_fusion['spread_total'] = df_fusion[f'z_score_{par1}'] + df_fusion[f'z_score_{par2}']

    # 5. Limpieza Final
    print("🧹 Limpiando ventanas incompletas...")
    df_fusion.dropna(inplace=True)

    # 6. Guardar el Dataset Final para Machine Learning
    if not os.path.exists("Data_Lake/Pares_Arbitraje"):
        os.makedirs("Data_Lake/Pares_Arbitraje")
        
    ruta_salida = f"Data_Lake/Pares_Arbitraje/Dataset_ML_{par1}_{par2}.csv"
    
    # Lo guardamos en CSV, que es el estándar nativo que usan las librerías de IA
    df_fusion.to_csv(ruta_salida, index=False)
    
    print("=======================================================")
    print(f"✅ ¡DATASET MAESTRO CREADO CON ÉXITO!")
    print(f"Ruta: {ruta_salida}")
    print(f"Total de registros viables: {len(df_fusion)}")
    print("=======================================================")

if __name__ == "__main__":
    fusionar_bases_de_datos(PAR_1, PAR_2)