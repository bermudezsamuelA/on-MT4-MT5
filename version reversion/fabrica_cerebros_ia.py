from fusionador_ml import fusionar_bases_de_datos
from etiquetador_ml import crear_etiquetas_machine_learning
from entrenador_ia import entrenar_modelo

# 🎯 Sincronizado exactamente con los pares activos de tu bot_daemon
PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"),
    ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"),
    ("EURUSD", "USDCHF"),
    ("NZDUSD", "USDCHF"),
    ("AUDUSD", "USDCAD")
]

def arrancar_fabrica():
    print("🚀 INICIANDO PRODUCCIÓN DE MODELOS DE IA (FASE 2: COINTEGRACIÓN INSTITUCIONAL)...\n")
    
    for par1, par2 in PARES_ACTIVOS:
        print(f"⚙️ Procesando matemática y regresión lineal para: {par1} vs {par2}")
        
        # 1. Extraer y fusionar (Ahora usa Logaritmos y Hedge Ratio β)
        df_fusionado = fusionar_bases_de_datos(par1, par2)
        if df_fusionado is None: continue
            
        # 2. Viajar al futuro y etiquetar el Spread Residual
        df_etiquetado = crear_etiquetas_machine_learning(df_fusionado)
        
        # 3. Entrenar y guardar los nuevos cerebros
        precision = entrenar_modelo(df_etiquetado, par1, par2)
        
        if precision:
            print(f"   ✅ Modelo Fase 2 Creado! Win Rate de la IA: {precision:.2f}%\n")

    print("🏆 TODAS LAS LÍNEAS DE PRODUCCIÓN HAN FINALIZADO. ARMAMENTO ACTUALIZADO.")

if __name__ == "__main__":
    arrancar_fabrica()