import sqlite3
import pandas as pd

def fusionar_bases_de_datos(par1, par2):
    try:
        conn1 = sqlite3.connect(f"Data_Lake/Monedas/{par1}.db")
        df1 = pd.read_sql_query("SELECT * FROM historico", conn1)
        conn1.close()
        
        conn2 = sqlite3.connect(f"Data_Lake/Monedas/{par2}.db")
        df2 = pd.read_sql_query("SELECT * FROM historico", conn2)
        conn2.close()
    except Exception as e:
        print(f" ❌ Faltan datos de {par1} o {par2}. Error: {e}")
        return None

    # Agregamos el sufijo del par a cada columna (excepto 'time') para no mezclar variables
    df1.columns = [f"{col}_{par1}" if col != 'time' else 'time' for col in df1.columns]
    df2.columns = [f"{col}_{par2}" if col != 'time' else 'time' for col in df2.columns]

    # Fusionamos respetando la línea temporal estricta
    df_fusion = pd.merge(df1, df2, on='time', how='inner')
    df_fusion.sort_values(by='time', inplace=True)
    df_fusion.reset_index(drop=True, inplace=True)

    if df_fusion.empty: 
        return None

    # El Z-score ya viene calculado desde el extractor_historico. Solo sumamos para el spread.
    df_fusion['spread_total'] = df_fusion[f'z_score_{par1}'] + df_fusion[f'z_score_{par2}']
    
    # Limpieza final
    df_fusion.dropna(inplace=True)

    return df_fusion