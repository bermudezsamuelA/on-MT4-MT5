import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score
import joblib
import os

def entrenar_modelo(df_entrenamiento, par1, par2):
    if not os.path.exists("Data_Lake/Modelos_IA"):
        os.makedirs("Data_Lake/Modelos_IA")

    df = df_entrenamiento.copy()
    df.reset_index(drop=True, inplace=True)

    # ==========================================
    # 1. SELECCIÓN DE FEATURES (Idioma H4 Estructural)
    # ==========================================
    features = []
    
    # Estas son las variables exactas que escupió el Extractor H4
    variables_base = [
        'ADX_14', 
        'ATRr_14', 
        'riesgo_pips_crudo', 
        'gatillo_pullback',
        'vela_indecision'
    ]
    
    for var in variables_base:
        col_p1 = f"{var}_{par1}"
        col_p2 = f"{var}_{par2}"
        if col_p1 in df.columns: features.append(col_p1)
        if col_p2 in df.columns: features.append(col_p2)

    # En H4, y filtrando solo las entradas válidas, nos quedarán muchos menos datos
    if len(df) < 30: 
        print(f"   ⚠️ Pocos datos etiquetados ({len(df)}). Se omite el entrenamiento.")
        return None

    X = df[features]
    y = df['target_exito']

    # ==========================================
    # 2. VALIDACIÓN WALK-FORWARD + EMBARGO
    # ==========================================
    tscv = TimeSeriesSplit(n_splits=5)
    
    # max_depth bajo (5) para evitar que memorice el ruido, class_weight para el desbalance
    modelo = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, class_weight='balanced')
    
    print(f"\n   ⚙️ Evaluando Walk-Forward Estructural para {par1}-{par2}...")
    
    precisiones_historicas = []
    
    for train_index, test_index in tscv.split(X):
        # Embargo de 5 velas H4 (aprox 1 día) de separación entre entrenamiento y test
        embargo = 5 
        if len(train_index) > embargo:
            train_index = train_index[:-embargo]
            
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        modelo.fit(X_train, y_train)
        preds = modelo.predict(X_test)
        
        if sum(preds) > 0:
            prec = precision_score(y_test, preds, zero_division=0)
            precisiones_historicas.append(prec)

    # Entrenamiento final con toda la historia
    modelo.fit(X, y)

    # ==========================================
    # TABLERO DE CONTROL CUANTITATIVO
    # ==========================================
    print(f"   📊 REPORTE DEL CEREBRO ESTRUCTURAL (H4): {par1} vs {par2}")
    print("   " + "="*50)
    
    prec_media = np.mean(precisiones_historicas) * 100 if precisiones_historicas else 0
    print(f"   🛡️ Precisión Real Esperada (1:1.5 Riesgo/Beneficio): {prec_media:.1f}%")
    
    # En un sistema con ratio 1:1.5, el punto de equilibrio es 40% de Win Rate.
    if prec_media < 45:
        print("   ⚠️ ADVERTENCIA: Rentabilidad matemática en zona de peligro (< 45%).")
    else:
        print("   ✅ ESTADO: Sistema matemáticamente rentable.")

    print("\n   🕵️‍♂️ TOP 5 VARIABLES CLAVE:")
    pesos = pd.DataFrame({"Variable": features, "Importancia": modelo.feature_importances_})
    pesos = pesos.sort_values(by="Importancia", ascending=False)
    
    for _, fila in pesos.head(5).iterrows():
        print(f"      -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")
        
    print("   " + "="*50)

    ruta_salida = f"Data_Lake/Modelos_IA/Cerebro_{par1}_{par2}.pkl"
    joblib.dump(modelo, ruta_salida)
    
    return prec_media