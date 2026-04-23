import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report # Restaurado
import joblib
import os

def entrenar_modelo(df_entrenamiento, par1, par2):
    if not os.path.exists("Data_Lake/Modelos_IA"):
        os.makedirs("Data_Lake/Modelos_IA")

    columnas_z_score = [col for col in df_entrenamiento.columns if 'z_score' in col]
    columnas_distancias = [col for col in df_entrenamiento.columns if 'distancia' in col]
    columnas_rsi = [col for col in df_entrenamiento.columns if 'RSI' in col]
    
    features = ['spread_total'] + columnas_z_score + columnas_distancias + columnas_rsi
    df_limpio = df_entrenamiento.dropna(subset=features).copy()
    
    if len(df_limpio) < 200:
        print(f"   ⚠️ Pocos datos etiquetados ({len(df_limpio)}). Se omite el entrenamiento.")
        return None

    X = df_limpio[features]
    y = df_limpio['target_exito']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, shuffle=False)

    modelo = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)

    predicciones = modelo.predict(X_test)
    precision_global = accuracy_score(y_test, predicciones) * 100

    # ==========================================
    # EL TABLERO DE CONTROL (Restaurado)
    # ==========================================
    print(f"\n   📊 REPORTE DEL CEREBRO: {par1} vs {par2}")
    print("   " + "="*45)
    
    # Reporte detallado (Precision, Recall, F1)
    reporte = classification_report(y_test, predicciones, target_names=["Perdedoras (0)", "Ganadoras (1)"])
    for linea in reporte.split('\n'):
        print(f"   {linea}")

    # Top 3 de variables que mira la IA
    print("   🕵️‍♂️ TOP 3 VARIABLES CLAVE:")
    importancias = modelo.feature_importances_
    pesos = pd.DataFrame({"Variable": features, "Importancia": importancias})
    pesos = pesos.sort_values(by="Importancia", ascending=False)
    
    for _, fila in pesos.head(3).iterrows():
        print(f"      -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")
        
    print("   " + "="*45)

    ruta_salida = f"Data_Lake/Modelos_IA/Cerebro_{par1}_{par2}.pkl"
    joblib.dump(modelo, ruta_salida)
    
    return precision_global