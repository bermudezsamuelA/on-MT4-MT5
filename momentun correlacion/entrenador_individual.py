import sqlite3
import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score
import joblib
import os

# ==========================================
# CONFIGURACIÓN
# ==========================================
MONEDAS = ["EURUSD", "GBPUSD", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD", "AUDJPY"]
VELAS_FUTURO_MAX = 42
RATIO_RB = 1.2

def etiquetar_y_entrenar(simbolo):
    print(f"\n⚙️ Entrenando Cerebro Especialista: {simbolo}")
    
    # 1. CARGA DE DATOS
    try:
        conn = sqlite3.connect(f"Data_Lake/Monedas/{simbolo}.db")
        df = pd.read_sql_query("SELECT * FROM historico", conn)
        conn.close()
    except Exception:
        print(f"   ❌ Base de datos no encontrada para {simbolo}.")
        return

    # 2. FILTRADO (Solo vemos donde hubo acción limpia)
    mascara = (df['gatillo_pullback'] != 0) & (df['vela_indecision'] == 0)
    df_entradas = df[mascara].copy()
    
    if len(df_entradas) < 30:
        print(f"   ⚠️ Muy pocas entradas limpias ({len(df_entradas)}). Se omite.")
        return

    print(f"   🎯 Analizando {len(df_entradas)} setups históricos de {simbolo}...")
    
    # 3. ETIQUETADO ESTRUCTURAL (Simulador 1:1.2)
    df_entradas['target_exito'] = np.nan
    
    for i in df_entradas.index:
        if i + VELAS_FUTURO_MAX >= len(df): continue
            
        gatillo = df.loc[i, 'gatillo_pullback']
        precio_entrada = df.loc[i, 'close']
        sl_estructural = df.loc[i, 'sl_estructural']
        riesgo = df.loc[i, 'riesgo_pips_crudo']
        
        resultado = 0
        
        if gatillo == 1: # LONG
            tp_estructural = precio_entrada + (riesgo * RATIO_RB)
            for j in range(1, VELAS_FUTURO_MAX + 1):
                futuro_high = df.loc[i+j, 'high']
                futuro_low = df.loc[i+j, 'low']
                if futuro_low <= sl_estructural: resultado = 0; break
                if futuro_high >= tp_estructural: resultado = 1; break
                    
        elif gatillo == -1: # SHORT
            tp_estructural = precio_entrada - (riesgo * RATIO_RB)
            for j in range(1, VELAS_FUTURO_MAX + 1):
                futuro_high = df.loc[i+j, 'high']
                futuro_low = df.loc[i+j, 'low']
                if futuro_high >= sl_estructural: resultado = 0; break
                if futuro_low <= tp_estructural: resultado = 1; break
                    
        df_entradas.at[i, 'target_exito'] = resultado

    df_limpio = df_entradas.dropna(subset=['target_exito']).copy()
    
    # Aquí están inyectadas las zonas de Fibonacci y la profundidad del pullback
    # 4. ENTRENAMIENTO DE LA IA (Anatomía Completa)
    features = [
        'ADX_14', 
        'ATRr_14', 
        'riesgo_pips_crudo', 
        'RSI_14', 
        'distancia_sma200',
        'profundidad_pb_atr', 
        'dist_fib_50',  
        'dist_fib_61'
    ]
    
    # Filtro de seguridad por si alguna columna no bajó bien
    features_disponibles = [f for f in features if f in df_limpio.columns]
    
    X = df_limpio[features_disponibles]
    y = df_limpio['target_exito'].astype(int)

    tscv = TimeSeriesSplit(n_splits=5)
    modelo = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, class_weight='balanced')
    
    precisiones_historicas = []
    
    for train_index, test_index in tscv.split(X):
        embargo = 5
        if len(train_index) > embargo: train_index = train_index[:-embargo]
            
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        modelo.fit(X_train, y_train)
        preds = modelo.predict(X_test)
        
        if sum(preds) > 0:
            prec = precision_score(y_test, preds, zero_division=0)
            precisiones_historicas.append(prec)

    modelo.fit(X, y)

    # 5. REPORTE
    print(f"   📊 REPORTE DEL CEREBRO: {simbolo}")
    print("   " + "="*40)
    prec_media = np.mean(precisiones_historicas) * 100 if precisiones_historicas else 0
    print(f"   🛡️ Win Rate Esperado (1:1.2): {prec_media:.1f}%")
    
    if prec_media < 45.5: print("   ⚠️ ADVERTENCIA: Sistema matemáticamente no rentable.")
    else: print("   ✅ ESTADO: Sistema rentable (>45.5%).")

    print("\n   🕵️‍♂️ VARIABLES QUE DECIDEN EL DISPARO:")
    importancias = modelo.feature_importances_
    pesos = pd.DataFrame({"Variable": features_disponibles, "Importancia": importancias})
    pesos = pesos.sort_values(by="Importancia", ascending=False)
    
    for _, fila in pesos.iterrows():
        print(f"      -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")
    print("   " + "="*40)

    if not os.path.exists("Data_Lake/Modelos_IA"): os.makedirs("Data_Lake/Modelos_IA")
    joblib.dump(modelo, f"Data_Lake/Modelos_IA/Cerebro_{simbolo}.pkl")

if __name__ == "__main__":
    print("🚀 INICIANDO ENTRENAMIENTO INDIVIDUAL DE MONEDAS...")
    for moneda in MONEDAS:
        etiquetar_y_entrenar(moneda)