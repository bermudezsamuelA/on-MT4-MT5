import pandas as pd
import numpy as np
from fusionador_ml import fusionar_bases_de_datos 

PARES_ACTIVOS = [
    ("GBPUSD", "USDCAD"),
    ("GBPUSD", "USDCHF"),
    ("EURUSD", "USDCAD"),
    ("EURUSD", "USDCHF"),
    ("NZDUSD", "USDCHF"),
    ("AUDUSD", "USDCAD")
]

VELAS_FUTURO = 48
GANANCIA_MINIMA_ATR = 1.0 # Solo medimos el dolor de las operaciones que ganaron al menos 1 ATR

def analizar_riesgo_momentum():
    print("🔍 INICIANDO PERFILADO DE RIESGO INSTITUCIONAL (MAE / MFE en ATR)\n")
    
    riesgo_optimo = {}

    for par1, par2 in PARES_ACTIVOS:
        print(f"⚙️ Procesando histórico en memoria para {par1} vs {par2}...")
        df = fusionar_bases_de_datos(par1, par2)
        
        if df is None or df.empty:
            print(f"   ❌ No se pudieron fusionar los datos.")
            continue
            
        df.reset_index(drop=True, inplace=True)
        
        # Evaluamos el riesgo de cada moneda de forma independiente
        for moneda in [par1, par2]:
            col_gatillo = f'gatillo_pullback_{moneda}'
            col_atr = f'ATRr_14_{moneda}'
            col_close = f'close_{moneda}'
            col_high = f'high_{moneda}'
            col_low = f'low_{moneda}'
            
            # Filtro de seguridad
            if col_gatillo not in df.columns:
                continue
                
            # Extraemos SOLO las filas donde el escáner ordenó disparar
            entradas = df[df[col_gatillo] != 0].index
            
            mae_list = [] # Maximum Adverse Excursion (Dolor soportado en ATR)
            mfe_list = [] # Maximum Favorable Excursion (Ganancia máxima en ATR)
            
            for i in entradas:
                if i + VELAS_FUTURO >= len(df): continue
                
                gatillo = df.loc[i, col_gatillo]
                precio = df.loc[i, col_close]
                atr = df.loc[i, col_atr]
                
                if atr == 0 or pd.isna(atr): continue
                
                # Proyección a futuro
                futuro_high = df.loc[i+1 : i+VELAS_FUTURO, col_high]
                futuro_low = df.loc[i+1 : i+VELAS_FUTURO, col_low]
                
                # Cálculo de recorrido crudo
                if gatillo == 1: # LONG
                    mfe = (futuro_high.max() - precio) / atr
                    mae = (precio - futuro_low.min()) / atr
                else: # SHORT
                    mfe = (precio - futuro_low.min()) / atr
                    mae = (futuro_high.max() - precio) / atr
                    
                mfe_list.append(mfe)
                
                # Filtro MAE: Solo guardamos el retroceso de las operaciones que terminaron ganando
                if mfe >= GANANCIA_MINIMA_ATR:
                    mae_list.append(mae)
                    
            if len(mae_list) < 30:
                print(f"   ⚠️ {moneda}: Pocos datos de victorias claras ({len(mae_list)}).")
            else:
                # El 95% de las VICTORIAS no retrocedió más que este nivel
                sl_atr = np.percentile(mae_list, 95) 
                # El 50% de las operaciones alcanzaron al menos este profit
                tp_atr = np.percentile(mfe_list, 50)
                
                print(f"   📊 {moneda}: {len(mae_list)} victorias analizadas.")
                print(f"      🛡️ SL Óptimo: {sl_atr:.2f} ATR")
                print(f"      🎯 TP Óptimo: {tp_atr:.2f} ATR")
                
                riesgo_optimo[moneda] = {"sl_atr": round(sl_atr, 2), "tp_atr": round(tp_atr, 2)}
        print("   -------------------------------------------------")
        
    return riesgo_optimo

if __name__ == "__main__":
    analizar_riesgo_momentum()