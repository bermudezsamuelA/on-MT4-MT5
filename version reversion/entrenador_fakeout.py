import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

# Importamos la función de tu archivo anterior
from etiquetador_fakeout import crear_dataset_fakeout

MONEDAS = ["GBPUSD", "USDCAD", "USDCHF", "EURUSD", "NZDUSD", "AUDUSD"]

def entrenar_modelos_fakeout():
    if not os.path.exists("Data_Lake/Modelos_IA"):
        os.makedirs("Data_Lake/Modelos_IA")

    print("🚀 INICIANDO ENTRENAMIENTO DE CAZADORES DE TRAMPAS (FAKEOUTS)...")

    for simbolo in MONEDAS:
        # 1. Extraemos y etiquetamos los datos en tiempo real
        df = crear_dataset_fakeout(simbolo)
        
        if df is None or len(df) < 200:
            print(f"   ⚠️ Saltando {simbolo} por falta de datos.\n")
            continue

        # 2. Separar Variables (X) y El Objetivo (y)
        X = df.drop(columns=['target_fakeout'])
        y = df['target_fakeout']

        # 3. Viaje en el tiempo (80% pasado para entrenar, 20% futuro para probar)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, shuffle=False)

        # 4. El Cerebro (Bosque Aleatorio)
        # IMPORTANTE: class_weight='balanced' le dice a la IA que preste más atención
        # a los Fakeouts (1) porque ocurren menos veces que los rompimientos reales (0).
        modelo = RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42, class_weight='balanced')
        modelo.fit(X_train, y_train)

        # 5. Examen Final
        predicciones = modelo.predict(X_test)

        print(f"\n   🧠 REPORTE DEL CAZADOR FAKEOUT: {simbolo}")
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

        # 6. Guardar el cerebro
        ruta_salida = f"Data_Lake/Modelos_IA/Fakeout_{simbolo}.pkl"
        joblib.dump(modelo, ruta_salida)

if __name__ == "__main__":
    entrenar_modelos_fakeout()