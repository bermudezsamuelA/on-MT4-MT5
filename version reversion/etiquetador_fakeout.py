import sqlite3
import pandas as pd
import numpy as np
import pandas_ta as ta
import os

VELAS_FUTURO = 15      # Tiempo máximo para darle la razón al movimiento (15 horas)
MULTIPLICADOR_ATR = 1.5 # Distancia que confirma un rompimiento real

def crear_dataset_fakeout(simbolo):
    print(f"🔍 Escaneando trampas de liquidez en {simbolo}...")
    ruta_db = f"Data_Lake/Monedas/{simbolo}.db"
    
    if not os.path.exists(ruta_db):
        print(f"   ❌ No se encontró la base de datos de {simbolo}.")
        return None

    # 1. Cargar la historia profunda
    conn = sqlite3.connect(ruta_db)
    df = pd.read_sql_query("SELECT * FROM historico", conn)
    conn.close()

    # Renombrar columnas si es necesario para compatibilidad con pandas_ta
    df.rename(columns={'tick_volume': 'volume'}, inplace=True)

    # 2. Inyección de Indicadores Matemáticos (Las armas del Quant)
    df.ta.bbands(length=20, std=2.0, append=True) # Volatilidad (Squeeze)
    df.ta.atr(length=14, append=True)             # Distancia promedio
    df.ta.rsi(length=14, append=True)             # Agotamiento
    df['VOL_SMA'] = df['volume'].rolling(20).mean() # Volumen promedio

    # Filtramos la data nula inicial
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Nombres de las columnas generadas por pandas_ta (Búsqueda Dinámica)
    col_bbl = [c for c in df.columns if c.startswith('BBL')][0]
    col_bbu = [c for c in df.columns if c.startswith('BBU')][0]
    col_sma = [c for c in df.columns if c.startswith('BBM')][0] 
    col_atr = [c for c in df.columns if c.startswith('ATR')][0]
    col_rsi = [c for c in df.columns if c.startswith('RSI')][0]

    # Features (Lo que la IA mirará para predecir)
    df['distancia_bbu'] = df['close'] - df[col_bbu]
    df['distancia_bbl'] = df['close'] - df[col_bbl]
    df['ratio_volumen'] = df['volume'] / df['VOL_SMA'] # ¿Hay inyección institucional?
    
    # 3. Detectar los Rompimientos (Los Gatillos)
    df['rompimiento_alcista'] = (df['close'] > df[col_bbu]) & (df['close'].shift(1) <= df[col_bbu].shift(1))
    df['rompimiento_bajista'] = (df['close'] < df[col_bbl]) & (df['close'].shift(1) >= df[col_bbl].shift(1))

    df['target_fakeout'] = np.nan

    # 4. Viaje al Futuro: Etiquetando la realidad
    eventos_analizados = 0
    trampas_detectadas = 0

    for i in range(len(df) - VELAS_FUTURO):
        es_alcista = df.loc[i, 'rompimiento_alcista']
        es_bajista = df.loc[i, 'rompimiento_bajista']
        
        if not es_alcista and not es_bajista:
            continue
            
        eventos_analizados += 1
        ventana_futura = df.loc[i+1 : i+VELAS_FUTURO]
        
        precio_entrada = df.loc[i, 'close']
        atr_actual = df.loc[i, col_atr]
        sma_actual = df.loc[i, col_sma]

        if es_alcista:
            # Reversión (Fakeout) toca la SMA. Rompimiento real sigue subiendo (ATR * 1.5)
            nivel_exito_real = precio_entrada + (atr_actual * MULTIPLICADOR_ATR)
            nivel_trampa = sma_actual
            
            for _, vela_futura in ventana_futura.iterrows():
                if vela_futura['high'] >= nivel_exito_real:
                    df.at[i, 'target_fakeout'] = 0 # Rompimiento Real
                    break
                elif vela_futura['low'] <= nivel_trampa:
                    df.at[i, 'target_fakeout'] = 1 # ¡TRAMPA DE LIQUIDEZ! (Fakeout)
                    trampas_detectadas += 1
                    break

        elif es_bajista:
            # Reversión (Fakeout) toca la SMA. Rompimiento real sigue bajando
            nivel_exito_real = precio_entrada - (atr_actual * MULTIPLICADOR_ATR)
            nivel_trampa = sma_actual
            
            for _, vela_futura in ventana_futura.iterrows():
                if vela_futura['low'] <= nivel_exito_real:
                    df.at[i, 'target_fakeout'] = 0 # Rompimiento Real
                    break
                elif vela_futura['high'] >= nivel_trampa:
                    df.at[i, 'target_fakeout'] = 1 # ¡TRAMPA DE LIQUIDEZ! (Fakeout)
                    trampas_detectadas += 1
                    break

    # Filtrar solo los momentos donde hubo un evento con etiqueta clara
    df_entrenamiento = df.dropna(subset=['target_fakeout']).copy()
    
    print(f"   📊 Resumen {simbolo}:")
    print(f"      -> Total Rompimientos: {eventos_analizados}")
    print(f"      -> Trampas Confirmadas (Fakeouts): {trampas_detectadas}")
    print(f"      -> Rompimientos Reales: {eventos_analizados - trampas_detectadas}")
    print("   -------------------------------------------------")
    
    # Nos quedamos con las variables vitales para la IA
    columnas_ia = [col_atr, col_rsi, 'ratio_volumen', 'distancia_bbu', 'distancia_bbl', 'target_fakeout']
    return df_entrenamiento[columnas_ia]

# Test Rápido
if __name__ == "__main__":
    df_fakeout = crear_dataset_fakeout("EURUSD")
    if df_fakeout is not None:
        print(df_fakeout.head())