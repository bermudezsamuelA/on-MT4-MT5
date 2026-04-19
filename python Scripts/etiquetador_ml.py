import pandas as pd
import numpy as np

# ==========================================
# CONFIGURACIÓN DEL ETIQUETADOR
# ==========================================
ARCHIVO_ENTRADA = "Data_Lake/Pares_Arbitraje/Dataset_ML_EURUSD_USDCHF.csv"
ARCHIVO_SALIDA = "Data_Lake/Pares_Arbitraje/Dataset_FINAL_EURUSD_USDCHF.csv"

# ¿Cuántas horas le damos al mercado para que el Spread regrese a cero?
VELAS_FUTURO = 24 

def crear_etiquetas_machine_learning():
    print(f"📥 Cargando dataset maestro: {ARCHIVO_ENTRADA}")
    df = pd.read_csv(ARCHIVO_ENTRADA)
    
    print(f"🔮 Mirando {VELAS_FUTURO} horas hacia el futuro para etiquetar operaciones...")
    
    # Creamos una columna vacía para nuestro "Target" (La respuesta del examen)
    # 1 = El spread convergió (Ganamos)
    # 0 = El spread siguió divergente o no hizo nada (Perdimos)
    df['target_exito'] = np.nan
    
    # Calculamos el spread futuro desplazando la columna hacia arriba (Shift negativo)
    df['spread_futuro'] = df['spread_total'].shift(-VELAS_FUTURO)
    
    # Lógica de Etiquetado de Arbitraje
    for i in range(len(df) - VELAS_FUTURO):
        spread_actual = df.loc[i, 'spread_total']
        spread_fut = df.loc[i, 'spread_futuro']
        
        # Solo nos interesan los momentos donde hubo una "Falla en la Matrix" real
        if spread_actual > 1.5:
            # Si estaba muy arriba, el éxito es que BAJE hacia cero
            if spread_fut < spread_actual:
                df.at[i, 'target_exito'] = 1
            else:
                df.at[i, 'target_exito'] = 0
                
        elif spread_actual < -1.5:
            # Si estaba muy abajo, el éxito es que SUBA hacia cero
            if spread_fut > spread_actual:
                df.at[i, 'target_exito'] = 1
            else:
                df.at[i, 'target_exito'] = 0

    # Limpiamos las últimas filas que no tienen futuro para mirar, 
    # y las filas aburridas (spread entre -1.5 y 1.5) donde no hubiéramos operado
    df_entrenamiento = df.dropna(subset=['target_exito']).copy()
    
    # Convertimos a entero para que la IA lo entienda mejor
    df_entrenamiento['target_exito'] = df_entrenamiento['target_exito'].astype(int)
    
    # Eliminamos la columna temporal 'spread_futuro' para no hacer trampa en el entrenamiento
    df_entrenamiento.drop(columns=['spread_futuro'], inplace=True)
    
    print(f"💾 Guardando Dataset Final etiquetado en: {ARCHIVO_SALIDA}")
    df_entrenamiento.to_csv(ARCHIVO_SALIDA, index=False)
    
    # --- ESTADÍSTICAS DEL EXAMEN ---
    total = len(df_entrenamiento)
    ganadas = df_entrenamiento['target_exito'].sum()
    win_rate = (ganadas / total) * 100
    
    print("\n=======================================================")
    print("   ✅ INGENIERÍA DE DATOS FINALIZADA")
    print("=======================================================")
    print(f"Operaciones de Arbitraje analizadas: {total}")
    print(f"Ganancias teóricas (Convergencias): {ganadas}")
    print(f"Win Rate Base del Mercado: {win_rate:.2f}%")
    print("=======================================================\n")
    print("El archivo Dataset_FINAL está listo para inyectarse en scikit-learn.")

if __name__ == "__main__":
    crear_etiquetas_machine_learning()