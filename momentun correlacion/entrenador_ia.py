import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, precision_score
import joblib
import os

def entrenar_modelo(df_entrenamiento, par1, par2):
    if not os.path.exists("Data_Lake/Modelos_IA"):
        os.makedirs("Data_Lake/Modelos_IA")

    df = df_entrenamiento.copy()

    # ==========================================
    # 1. ENRIQUECIMIENTO DEL SPREAD (Punto 5)
    # ==========================================
    # Ya no le damos solo el spread crudo, le damos su contexto dinámico
    df['spread_sma_20'] = df['spread_total'].rolling(20).mean()
    df['spread_std_20'] = df['spread_total'].rolling(20).std()
    df['spread_slope_5'] = df['spread_total'] - df['spread_total'].shift(5) # Pendiente
    
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ==========================================
    # 2. SELECCIÓN DE FEATURES 
    # ==========================================
    features = ['spread_total', 'spread_sma_20', 'spread_std_20', 'spread_slope_5']
    
    variables_base = [
        'z_score', 'ADX_14', 'ATRr_14', 
        'profundidad_pullback_atr', 'gatillo_pullback', 'en_zona_kmeans'
    ]
    
    for var in variables_base:
        col_p1 = f"{var}_{par1}"
        col_p2 = f"{var}_{par2}"
        if col_p1 in df.columns: features.append(col_p1)
        if col_p2 in df.columns: features.append(col_p2)

    if len(df) < 500:
        print(f"   ⚠️ Pocos datos para Walk-Forward ({len(df)}). Se omite el entrenamiento.")
        return None

    X = df[features]
    y = df['target_exito']

    # ==========================================
    # 3. VALIDACIÓN WALK-FORWARD + EMBARGO (Puntos 3 y 6)
    # ==========================================
    # Dividimos la historia en 5 bloques de tiempo progresivos
    tscv = TimeSeriesSplit(n_splits=5)
    
    # Reducimos max_depth para evitar sobreajuste (Overfitting)
    modelo = RandomForestClassifier(n_estimators=200, max_depth=7, random_state=42, class_weight='balanced')
    
    print(f"\n   ⚙️ Evaluando con Walk-Forward (5 Folds) para {par1}-{par2}...")
    
    precisiones_historicas = []
    
    for train_index, test_index in tscv.split(X):
        # EMBARGO: Eliminamos las últimas 24 velas del set de entrenamiento
        # para que no haya fuga de datos hacia el futuro del set de prueba.
        embargo = 24 
        if len(train_index) > embargo:
            train_index = train_index[:-embargo]
            
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        # Entrenamos en el pasado, predecimos en el futuro iterativo
        modelo.fit(X_train, y_train)
        preds = modelo.predict(X_test)
        
        # Métrica de Trading (Punto 4): Nos importa la PRECISION (Cuando dice dispara, ¿gana?)
        if sum(preds) > 0:
            prec = precision_score(y_test, preds, zero_division=0)
            precisiones_historicas.append(prec)

    # Una vez validada la robustez, entrenamos el modelo FINAL con todo el dataset
    modelo.fit(X, y)

    # ==========================================
    # EL TABLERO DE CONTROL CUANTITATIVO
    # ==========================================
    print(f"   📊 REPORTE DEL CEREBRO MOMENTUM: {par1} vs {par2}")
    print("   " + "="*50)
    
    prec_media = np.mean(precisiones_historicas) * 100 if precisiones_historicas else 0
    print(f"   🛡️ Precisión Real Esperada (Walk-Forward): {prec_media:.1f}%")
    
    if prec_media < 55:
        print("   ⚠️ ADVERTENCIA: Este modelo tiene una ventaja estadística pobre en el tiempo.")

    print("\n   🕵️‍♂️ TOP 5 VARIABLES CLAVE:")
    pesos = pd.DataFrame({"Variable": features, "Importancia": modelo.feature_importances_})
    pesos = pesos.sort_values(by="Importancia", ascending=False)
    
    for _, fila in pesos.head(5).iterrows():
        print(f"      -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")
        
    print("   " + "="*50)

    ruta_salida = f"Data_Lake/Modelos_IA/Cerebro_{par1}_{par2}.pkl"
    joblib.dump(modelo, ruta_salida)
    
    return prec_media