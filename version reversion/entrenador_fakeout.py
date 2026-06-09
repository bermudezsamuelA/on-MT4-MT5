import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

from etiquetador_fakeout import crear_dataset_fakeout

MONEDAS = ["GBPUSD", "USDCAD", "USDCHF", "EURUSD", "NZDUSD", "AUDUSD"]

def entrenar_modelos_fakeout():
    if not os.path.exists("Data_Lake/Modelos_IA"):
        os.makedirs("Data_Lake/Modelos_IA")

    print("🚀 INICIANDO ENTRENAMIENTO DE CAZADORES DE TRAMPAS (XGBOOST)...")

    for simbolo in MONEDAS:
        df = crear_dataset_fakeout(simbolo)
        
        if df is None or len(df) < 200:
            print(f"   ⚠️ Saltando {simbolo} por falta de datos.\n")
            continue

        X = df.drop(columns=['target_fakeout'])
        y = df['target_fakeout']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, shuffle=False)

        # 🧠 FASE 3: XGBoost (Gradient Boosting)
        ratio_clases = (len(y_train) - sum(y_train)) / sum(y_train) if sum(y_train) > 0 else 1
        
        modelo = XGBClassifier(
            n_estimators=300, 
            max_depth=6, 
            learning_rate=0.05, 
            random_state=42, 
            scale_pos_weight=ratio_clases,
            eval_metric='logloss'
        )
        modelo.fit(X_train, y_train)

        predicciones = modelo.predict(X_test)

        print(f"\n   🧠 REPORTE CAZADOR XGBOOST: {simbolo}")
        print("   " + "="*45)
        
        reporte = classification_report(y_test, predicciones, target_names=["Rompimiento Real (0)", "Trampa/Fakeout (1)"])
        for linea in reporte.split('\n'):
            print(f"   {linea}")

        print("   🕵️‍♂️ QUÉ MIRA LA IA PARA DETECTAR LA TRAMPA:")
        importancias = modelo.feature_importances_
        pesos = pd.DataFrame({"Variable": X.columns, "Importancia": importancias})
        pesos = pesos.sort_values(by="Importancia", ascending=False)
        for _, fila in pesos.head(3).iterrows():
            print(f"      -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")
        print("   " + "="*45 + "\n")

        ruta_salida = f"Data_Lake/Modelos_IA/Fakeout_{simbolo}.pkl"
        joblib.dump(modelo, ruta_salida)

if __name__ == "__main__":
    entrenar_modelos_fakeout()