import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import sqlite3
import os
import argparse
from scipy.signal import find_peaks

# ==========================================
# CONFIGURACIÓN DEL EXTRACTOR H4 (AVANZADO)
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H4  
VELAS_TOTALES = 15000            
VENTANA_ESTRUCTURA = 40          
ADX_UMBRAL = 25

def configurar_carpetas():
    if not os.path.exists("Data_Lake/Monedas"):
        os.makedirs("Data_Lake/Monedas")

def encontrar_estructura(df_slice, tendencia):
    if tendencia == 'ALCISTA':
        valles, _ = find_peaks(-df_slice['low'].values, distance=3)
        if len(valles) > 0:
            idx_valle = valles[-1]
            return df_slice['low'].iloc[idx_valle], df_slice['high'].max() # Retorna (Valle, Cima Previa)
        return df_slice['low'].min(), df_slice['high'].max()
    else:
        cimas, _ = find_peaks(df_slice['high'].values, distance=3)
        if len(cimas) > 0:
            idx_cima = cimas[-1]
            return df_slice['high'].iloc[idx_cima], df_slice['low'].min() # Retorna (Cima, Valle Previo)
        return df_slice['high'].max(), df_slice['low'].min()

def extraer_y_procesar(simbolo):
    print(f"\n[1/3] Descargando H4 de {simbolo}...")
    if not mt5.initialize():
        print("Error crítico: MT5 no inicializado")
        return

    mt5.symbol_select(simbolo, True)
    datos = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_TOTALES)
    mt5.shutdown()

    if datos is None: return

    df = pd.DataFrame(datos)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print("[2/3] Calculando Momentum y Osciladores...")
    df.ta.sma(length=200, append=True)
    df.ta.sma(length=20, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.rsi(length=14, append=True) 
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    col_sma200 = [c for c in df.columns if c.startswith('SMA_200')][0]
    col_sma20 = [c for c in df.columns if c.startswith('SMA_20')][0]
    col_adx = [c for c in df.columns if c.startswith('ADX')][0]
    col_dmp = [c for c in df.columns if c.startswith('DMP')][0] 
    col_dmn = [c for c in df.columns if c.startswith('DMN')][0] 
    col_atr = [c for c in df.columns if c.startswith('ATR')][0]
    col_rsi = [c for c in df.columns if c.startswith('RSI')][0]

    df['tendencia'] = np.where(df['close'] > df[col_sma200], 'ALCISTA', 'BAJISTA')
    df['distancia_sma200'] = abs(df['close'] - df[col_sma200]) / df[col_atr] 
    
    print("[3/3] Mapeando Anatomía del Pullback y Fibonacci...")
    
    sl_estructural = []
    distancia_sl = []
    indecision = []
    gatillos = []
    profundidad_pullback = []
    
    # NUEVO: Listas para guardar las distancias continuas vela a vela
    lista_dist_fib_50 = []
    lista_dist_fib_61 = []

    for i in range(len(df)):
        if i < VENTANA_ESTRUCTURA:
            sl_estructural.append(np.nan)
            distancia_sl.append(np.nan)
            indecision.append(1)
            gatillos.append(0)
            profundidad_pullback.append(np.nan)
            lista_dist_fib_50.append(np.nan)
            lista_dist_fib_61.append(np.nan)
            continue
            
        vela_actual = df.iloc[i]
        df_pasado = df.iloc[i - VENTANA_ESTRUCTURA : i]
        
        precio = vela_actual['close']
        atr = vela_actual[col_atr]
        tendencia = vela_actual['tendencia']
        
        # Filtro de Indecisión
        cuerpo_vela = abs(vela_actual['open'] - vela_actual['close'])
        tamaño_total = vela_actual['high'] - vela_actual['low']
        es_doji = 1 if (tamaño_total > 0 and cuerpo_vela / tamaño_total < 0.15) else 0
        indecision.append(es_doji)
        
        # Estructura y Fibonacci
        nivel_sl, extremo_previo = encontrar_estructura(df_pasado, tendencia)
        leg_size = abs(extremo_previo - nivel_sl)
        
        dist_riesgo = 0
        profundidad = 0
        dist_fib_50 = np.nan
        dist_fib_61 = np.nan
        
        if tendencia == 'ALCISTA':
            sl_final = nivel_sl - (atr * 0.2)
            dist_riesgo = precio - sl_final
            if leg_size > 0:
                profundidad = (extremo_previo - precio) / atr
                fib_50 = extremo_previo - (leg_size * 0.50)
                fib_61 = extremo_previo - (leg_size * 0.618)
                dist_fib_50 = abs(precio - fib_50) / atr
                dist_fib_61 = abs(precio - fib_61) / atr
        else:
            sl_final = nivel_sl + (atr * 0.2)
            dist_riesgo = sl_final - precio
            if leg_size > 0:
                profundidad = (precio - extremo_previo) / atr
                fib_50 = extremo_previo + (leg_size * 0.50)
                fib_61 = extremo_previo + (leg_size * 0.618)
                dist_fib_50 = abs(precio - fib_50) / atr
                dist_fib_61 = abs(precio - fib_61) / atr
                
        sl_estructural.append(sl_final)
        distancia_sl.append(dist_riesgo if dist_riesgo > 0 else atr) 
        profundidad_pullback.append(profundidad)
        lista_dist_fib_50.append(dist_fib_50)
        lista_dist_fib_61.append(dist_fib_61)
        
        # Gatillo de Pullback
        adx_pasado_max = df_pasado[col_adx].max()
        gatillo = 0
        
        if not es_doji and adx_pasado_max > ADX_UMBRAL:
            if tendencia == "ALCISTA" and vela_actual[col_dmp] > vela_actual[col_dmn]:
                if df.iloc[i-2:i+1]['low'].min() <= vela_actual[col_sma20] and precio > vela_actual[col_sma20]:
                    gatillo = 1
            elif tendencia == "BAJISTA" and vela_actual[col_dmn] > vela_actual[col_dmp]:
                if df.iloc[i-2:i+1]['high'].max() >= vela_actual[col_sma20] and precio < vela_actual[col_sma20]:
                    gatillo = -1
                    
        gatillos.append(gatillo)

    # Agregamos las columnas al DataFrame
    df['sl_estructural'] = sl_estructural
    df['riesgo_pips_crudo'] = distancia_sl
    df['vela_indecision'] = indecision
    df['gatillo_pullback'] = gatillos
    df['profundidad_pb_atr'] = profundidad_pullback
    df['dist_fib_50'] = lista_dist_fib_50
    df['dist_fib_61'] = lista_dist_fib_61

    df.dropna(inplace=True)

    db_path = f"Data_Lake/Monedas/{simbolo}.db"
    conexion = sqlite3.connect(db_path)
    df.to_sql("historico", conexion, if_exists="replace", index=False)
    conexion.close()
    
    print(f"✅ H4 procesado para {simbolo}. Registros útiles: {len(df)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("simbolo", type=str)
    args = parser.parse_args()
    
    configurar_carpetas()
    extraer_y_procesar(args.simbolo.upper())