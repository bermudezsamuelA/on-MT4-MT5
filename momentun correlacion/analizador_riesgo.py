import pandas as pd
import numpy as np
from fusionador_ml import fusionar_bases_de_datos # ⚡ Importamos los datos directos en RAM

PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"),
    ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"),
    ("EURUSD", "USDCHF"),
    ("NZDUSD", "USDCHF"),
    ("AUDUSD", "USDCAD")
]

VELAS_FUTURO = 24

def analizar_riesgo():
    print("🔍 INICIANDO ANÁLISIS CUANTITATIVO DE RIESGO (MAE / MFE)\n")
    
    for par1, par2 in PARES_ACTIVOS:
        print(f"⚙️ Procesando histórico en memoria para {par1} vs {par2}...")
        
        # Generamos el dataset en vivo sin usar archivos CSV
        df = fusionar_bases_de_datos(par1, par2)
        
        if df is None or df.empty:
            print(f"   ❌ No se pudieron fusionar los datos.\n")
            continue
            
        # Reiniciamos índice por seguridad
        df.reset_index(drop=True, inplace=True)
        
        excursiones_adversas = []
        excursiones_favorables = []
        
        for i in range(len(df) - VELAS_FUTURO):
            spread_actual = df.loc[i, 'spread_total']
            
            if abs(spread_actual) > 1.5:
                ventana = df.loc[i:i+VELAS_FUTURO, 'spread_total']
                
                if spread_actual > 1.5:
                    max_adverso = ventana.max() - spread_actual 
                    max_favorable = spread_actual - ventana.min() 
                else:
                    max_adverso = spread_actual - ventana.min() 
                    max_favorable = ventana.max() - spread_actual 
                
                if max_favorable > 1.0: 
                    excursiones_adversas.append(max_adverso)
                    excursiones_favorables.append(max_favorable)

        if len(excursiones_adversas) == 0:
            print("   ⚠️ No hay suficientes datos de victorias.\n")
            continue
            
        # El 95% de nuestras victorias NUNCA sufrieron más que este dolor
        sl_optimo = np.percentile(excursiones_adversas, 95)
        # El 50% de las veces, el precio llegó fácil hasta esta ganancia
        tp_optimo = np.percentile(excursiones_favorables, 50)
        
        multiplicador_sl = sl_optimo / 2.0
        multiplicador_tp = tp_optimo / 2.0
        
        print(f"📊 REPORTE DE RIESGO: {par1} vs {par2}")
        print(f"   📈 Victorias analizadas: {len(excursiones_adversas)} escenarios reales")
        print(f"   🛡️ Stop Loss Ideal  : {multiplicador_sl:.2f} * std_dev")
        print(f"   🎯 Take Profit Ideal: {multiplicador_tp:.2f} * std_dev")
        print("   -------------------------------------------------\n")

if __name__ == "__main__":
    analizar_riesgo()