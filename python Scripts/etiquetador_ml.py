import pandas as pd
import numpy as np

VELAS_FUTURO = 24 

def crear_etiquetas_machine_learning(df_fusion):
    df = df_fusion.copy()
    
    # 🛠️ LA SOLUCIÓN: Reiniciar el índice para que vuelva a empezar desde 0
    df.reset_index(drop=True, inplace=True)
    
    df['target_exito'] = np.nan
    df['spread_futuro'] = df['spread_total'].shift(-VELAS_FUTURO)
    
    for i in range(len(df) - VELAS_FUTURO):
        spread_actual = df.loc[i, 'spread_total']
        spread_fut = df.loc[i, 'spread_futuro']
        
        if spread_actual > 1.5:
            df.at[i, 'target_exito'] = 1 if spread_fut < spread_actual else 0
        elif spread_actual < -1.5:
            df.at[i, 'target_exito'] = 1 if spread_fut > spread_actual else 0

    df_entrenamiento = df.dropna(subset=['target_exito']).copy()
    df_entrenamiento['target_exito'] = df_entrenamiento['target_exito'].astype(int)
    df_entrenamiento.drop(columns=['spread_futuro'], inplace=True)
    
    return df_entrenamiento