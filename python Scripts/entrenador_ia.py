import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
ARCHIVO_DATASET = "Data_Lake/Pares_Arbitraje/Dataset_FINAL_EURUSD_USDCHF.csv"
MODELO_SALIDA = "Data_Lake/Cerebro_IA_Arbitraje.pkl"

def entrenar_modelo():
    print(f"🧠 Cargando conocimientos históricos desde: {ARCHIVO_DATASET}...")
    df = pd.read_csv(ARCHIVO_DATASET)

    # ==========================================
    # 2. SELECCIÓN DE VARIABLES (Feature Engineering)
    # ==========================================
    # Extraemos automáticamente las columnas que contienen la información valiosa
    columnas_z_score = [col for col in df.columns if 'z_score' in col]
    columnas_distancias = [col for col in df.columns if 'distancia' in col]
    columnas_rsi = [col for col in df.columns if 'RSI' in col]
    
    # Nuestras variables de entrada (X) y la respuesta del examen (y)
    features = ['spread_total'] + columnas_z_score + columnas_distancias + columnas_rsi
    
    # Limpiamos filas donde la ventana de K-Means aún no había encontrado soportes/resistencias
    df_limpio = df.dropna(subset=features).copy()
    
    X = df_limpio[features]
    y = df_limpio['target_exito']

    print(f"📊 Entrenando con {len(X)} escenarios de mercado altamente calificados...")

    # ==========================================
    # 3. DIVISIÓN DEL TIEMPO (Train/Test Split)
    # ==========================================
    # IMPORTANTE: shuffle=False para no viajar al futuro y arruinar el aprendizaje.
    # Entrenamos con el pasado antiguo (80%) y le tomamos examen con el pasado reciente (20%)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, shuffle=False)

    # ==========================================
    # 4. ENTRENAMIENTO DEL MODELO (Random Forest)
    # ==========================================
    print("⚙️ Cultivando el Bosque Aleatorio (Esto tomará unos segundos)...")
    modelo = RandomForestClassifier(
        n_estimators=200,      # 200 árboles tomando decisiones
        max_depth=10,          # Profundidad de la lógica para evitar sobreajuste
        random_state=42,
        class_weight='balanced' # Le da importancia a no fallar operaciones
    )
    
    modelo.fit(X_train, y_train)

    # ==========================================
    # 5. EXAMEN FINAL Y EVALUACIÓN
    # ==========================================
    predicciones = modelo.predict(X_test)
    precision = accuracy_score(y_test, predicciones) * 100

    print("\n=======================================================")
    print("   🏆 REPORTE DE INTELIGENCIA ARTIFICIAL")
    print("=======================================================")
    print(f"Precisión Predictiva (Win Rate de la IA): {precision:.2f}%\n")
    
    print("Desglose del Modelo:")
    print(classification_report(y_test, predicciones, target_names=["Perdedoras (0)", "Ganadoras (1)"]))

    # ==========================================
    # 6. ¿QUÉ APRENDIÓ LA MÁQUINA? (Feature Importance)
    # ==========================================
    print("\n🕵️‍♂️ PESO DE LAS VARIABLES (¿Qué mira la IA para decidir?):")
    importancias = modelo.feature_importances_
    pesos = pd.DataFrame({"Variable": features, "Importancia": importancias})
    pesos = pesos.sort_values(by="Importancia", ascending=False)
    
    for _, fila in pesos.head(5).iterrows():
        print(f" -> {fila['Variable']}: {fila['Importancia']*100:.1f}%")

    # ==========================================
    # 7. GUARDAR EL CEREBRO
    # ==========================================
    joblib.dump(modelo, MODELO_SALIDA)
    print("=======================================================")
    print(f"💾 Cerebro Cuantitativo guardado en: {MODELO_SALIDA}")
    print("Listo para ser conectado al bot en vivo.")

if __name__ == "__main__":
    entrenar_modelo()