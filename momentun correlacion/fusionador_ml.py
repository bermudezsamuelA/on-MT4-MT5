import sqlite3
import pandas as pd

VENTANA_Z_SCORE = 250

def fusionar_bases_de_datos(par1, par2):
    try:
        conn1 = sqlite3.connect(f"Data_Lake/Monedas/{par1}.db")
        df1 = pd.read_sql_query("SELECT * FROM historico", conn1)
        conn1.close()
        
        conn2 = sqlite3.connect(f"Data_Lake/Monedas/{par2}.db")
        df2 = pd.read_sql_query("SELECT * FROM historico", conn2)
        conn2.close()
    except Exception as e:
        print(f"   ❌ Faltan datos de {par1} o {par2}.")
        return None

    df1.columns = [f"{col}_{par1}" if col != 'time' else 'time' for col in df1.columns]
    df2.columns = [f"{col}_{par2}" if col != 'time' else 'time' for col in df2.columns]

    df_fusion = pd.merge(df1, df2, on='time', how='inner')
    df_fusion.sort_values(by='time', inplace=True)
    df_fusion.reset_index(drop=True, inplace=True)

    if df_fusion.empty: return None

    media_p1 = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).mean()
    std_p1 = df_fusion[f'close_{par1}'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion[f'z_score_{par1}'] = (df_fusion[f'close_{par1}'] - media_p1) / std_p1

    media_p2 = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).mean()
    std_p2 = df_fusion[f'close_{par2}'].rolling(window=VENTANA_Z_SCORE).std()
    df_fusion[f'z_score_{par2}'] = (df_fusion[f'close_{par2}'] - media_p2) / std_p2

    df_fusion['spread_total'] = df_fusion[f'z_score_{par1}'] + df_fusion[f'z_score_{par2}']
    df_fusion.dropna(inplace=True)

    return df_fusion