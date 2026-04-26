import pandas as pd
import numpy as np

# ==========================================
# REGLAS DEL SIMULADOR DE TRADE
# ==========================================
VELAS_FUTURO = 48        # Tiempo máximo para que la tendencia se desarrolle
TP_ATR = 1.0             # Take Profit: 1.0 veces el ATR
SL_ATR = 0.5             # Stop Loss: 0.5 veces el ATR (Ratio Riesgo:Beneficio 1:2)

def crear_etiquetas_machine_learning(df_fusion):
    df = df_fusion.copy()
    df.reset_index(drop=True, inplace=True)
    
    # 1. IDENTIFICACIÓN DE PARES
    # Extraemos los nombres de las monedas dinámicamente desde las columnas
    cols_close = [c for c in df.columns if c.startswith('close_')]
    if len(cols_close) < 2: return None
    par1 = cols_close[0].replace('close_', '')
    par2 = cols_close[1].replace('close_', '')
    
    col_gatillo_p1 = f'gatillo_pullback_{par1}'
    col_gatillo_p2 = f'gatillo_pullback_{par2}'
    col_atr_p1 = f'ATRr_14_{par1}'
    col_atr_p2 = f'ATRr_14_{par2}'

    # 2. FILTRO DE RUIDO (El punto más crítico de DeepSeek)
    # Entrenaremos a la IA SOLO con las filas donde el escáner detectó un Pullback real.
    if col_gatillo_p1 not in df.columns or col_gatillo_p2 not in df.columns:
        print("❌ Error: Faltan las columnas de gatillo. Ejecuta el extractor histórico primero.")
        return None

    mascara_entradas = (df[col_gatillo_p1] != 0) | (df[col_gatillo_p2] != 0)
    indices_entrada = df[mascara_entradas].index
    
    df['target_exito'] = np.nan
    
    # 3. SIMULADOR DE EJECUCIÓN (Vela a Vela)
    for i in indices_entrada:
        if i + VELAS_FUTURO >= len(df):
            continue # Descartar trades al final del dataset (futuro desconocido)
            
        gatillo_1 = df.loc[i, col_gatillo_p1]
        gatillo_2 = df.loc[i, col_gatillo_p2]
        
        resultado = 0 # Por defecto, la operación se considera perdedora o aburrida
        
        # --- EVALUACIÓN PAR 1 ---
        if gatillo_1 != 0:
            precio_entrada = df.loc[i, cols_close[0]]
            atr = df.loc[i, col_atr_p1]
            
            if gatillo_1 == 1: # COMPRA LONG
                tp = precio_entrada + (atr * TP_ATR)
                sl = precio_entrada - (atr * SL_ATR)
                
                for j in range(1, VELAS_FUTURO + 1):
                    futuro_high = df.loc[i+j, f'high_{par1}']
                    futuro_low = df.loc[i+j, f'low_{par1}']
                    if futuro_low <= sl:
                        resultado = 0; break # Tocó Stop Loss primero
                    if futuro_high >= tp:
                        resultado = 1; break # Tocó Take Profit primero
                        
            elif gatillo_1 == -1: # VENTA SHORT
                tp = precio_entrada - (atr * TP_ATR)
                sl = precio_entrada + (atr * SL_ATR)
                
                for j in range(1, VELAS_FUTURO + 1):
                    futuro_high = df.loc[i+j, f'high_{par1}']
                    futuro_low = df.loc[i+j, f'low_{par1}']
                    if futuro_high >= sl:
                        resultado = 0; break 
                    if futuro_low <= tp:
                        resultado = 1; break 
                        
        # --- EVALUACIÓN PAR 2 (Si el Par 1 no disparó) ---
        elif gatillo_2 != 0:
            precio_entrada = df.loc[i, cols_close[1]]
            atr = df.loc[i, col_atr_p2]
            
            if gatillo_2 == 1: # COMPRA
                tp = precio_entrada + (atr * TP_ATR)
                sl = precio_entrada - (atr * SL_ATR)
                for j in range(1, VELAS_FUTURO + 1):
                    futuro_high = df.loc[i+j, f'high_{par2}']
                    futuro_low = df.loc[i+j, f'low_{par2}']
                    if futuro_low <= sl: resultado = 0; break
                    if futuro_high >= tp: resultado = 1; break
                        
            elif gatillo_2 == -1: # VENTA
                tp = precio_entrada - (atr * TP_ATR)
                sl = precio_entrada + (atr * SL_ATR)
                for j in range(1, VELAS_FUTURO + 1):
                    futuro_high = df.loc[i+j, f'high_{par2}']
                    futuro_low = df.loc[i+j, f'low_{par2}']
                    if futuro_high >= sl: resultado = 0; break
                    if futuro_low <= tp: resultado = 1; break
        
        df.at[i, 'target_exito'] = resultado

    # 4. EXTRACCIÓN DEL DATASET LIMPIO
    # Retornamos ÚNICAMENTE las filas donde hubo un trade. El resto de las 60,000 velas se descarta.
    df_entrenamiento = df.dropna(subset=['target_exito']).copy()
    df_entrenamiento['target_exito'] = df_entrenamiento['target_exito'].astype(int)
    
    return df_entrenamiento