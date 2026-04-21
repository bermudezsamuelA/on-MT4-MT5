from fusionador_ml import fusionar_bases_de_datos
from etiquetador_ml import crear_etiquetas_machine_learning
from entrenador_ia import entrenar_modelo

PARES_INVERSOS = [
    ("EURUSD", "USDCHF"),
    ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"),
    ("GBPUSD", "USDCAD"),
    ("AUDUSD", "USDCAD"),
    ("NZDUSD", "USDCAD"),
    ("NZDUSD", "USDCHF"),
    ("AUDJPY", "USDCAD"),
]

def arrancar_fabrica():
    print("🚀 INICIANDO PRODUCCIÓN INDUSTRIAL DE MODELOS DE IA...\n")
    
    for par1, par2 in PARES_INVERSOS:
        print(f"⚙️ Procesando: {par1} vs {par2}")
        
        # 1. Extraer y fusionar
        df_fusionado = fusionar_bases_de_datos(par1, par2)
        if df_fusionado is None: continue
            
        # 2. Viajar al futuro y etiquetar
        df_etiquetado = crear_etiquetas_machine_learning(df_fusionado)
        
        # 3. Entrenar y guardar el cerebro
        precision = entrenar_modelo(df_etiquetado, par1, par2)
        
        if precision:
            print(f"   ✅ Modelo Creado! Win Rate de la IA: {precision:.2f}%\n")

    print("🏆 TODAS LAS LÍNEAS DE PRODUCCIÓN HAN FINALIZADO.")

if __name__ == "__main__":
    arrancar_fabrica()