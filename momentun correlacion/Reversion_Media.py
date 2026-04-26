import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta

# ==========================================
# 1. PARÁMETROS DEL SENSOR DE MOMENTUM
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H1 
VELAS_HISTORIAL = 300 

# Parámetros Matemáticos Institucionales (Trend-Following)
SMA_MACRO = 200      
SMA_MICRO = 20       
ADX_PERIOD = 14      
ADX_UMBRAL = 25      
ATR_PERIOD = 14
PULLBACK_ATR_MULT = 1.0 
VELAS_MEMORIA = 3    
VENTANA_IMPULSO = 40 # Cuántas velas miramos hacia atrás para encontrar la Pierna A->B

# ==========================================
# 2. MOTOR DE ANÁLISIS DE MOMENTUM Y PULLBACK
# ==========================================
def analizar_momentum_multimoneda(lista_monedas):
    if not mt5.initialize():
        print("❌ Error al inicializar MT5")
        return {}

    diagnostico_global = {}

    for simbolo in lista_monedas:
        velas = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_HISTORIAL)
        
        if velas is None or len(velas) < SMA_MACRO + ATR_PERIOD + 10:
            continue

        df = pd.DataFrame(velas)
        
        # --- INYECCIÓN DE INDICADORES ---
        df.ta.sma(length=SMA_MACRO, append=True)
        df.ta.sma(length=SMA_MICRO, append=True)
        df.ta.adx(length=ADX_PERIOD, append=True)
        df.ta.atr(length=ATR_PERIOD, append=True)
        
        df.dropna(inplace=True)
        if df.empty: continue

        col_sma200 = [c for c in df.columns if c.startswith(f'SMA_{SMA_MACRO}')][0]
        col_sma20 = [c for c in df.columns if c.startswith(f'SMA_{SMA_MICRO}')][0]
        col_adx = [c for c in df.columns if c.startswith('ADX')][0]
        col_dmp = [c for c in df.columns if c.startswith('DMP')][0]
        col_dmn = [c for c in df.columns if c.startswith('DMN')][0]
        col_atr = [c for c in df.columns if c.startswith('ATR')][0]

        velas_recientes = df.iloc[-(VELAS_MEMORIA + 1):-1]
        vela_actual_cerrada = df.iloc[-2]
        precio = vela_actual_cerrada['close']

        # --- LÓGICA DE DIAGNÓSTICO MACRO ---
        tendencia = "LATERAL"
        if precio > vela_actual_cerrada[col_sma200]: tendencia = "ALCISTA"
        elif precio < vela_actual_cerrada[col_sma200]: tendencia = "BAJISTA"

        fuerza = "DÉBIL (Rango)"
        if vela_actual_cerrada[col_adx] >= ADX_UMBRAL:
            fuerza = "FUERTE (Tendencia)"

        gatillo = None
        zona_pullback_atr = vela_actual_cerrada[col_atr] * PULLBACK_ATR_MULT
        
        # --- ANÁLISIS DE LA PIERNA IMPULSIVA Y FIBONACCI ---
        # Aislamos la ventana de tiempo reciente para buscar el impulso
        df_impulso = df.iloc[-(VENTANA_IMPULSO + 2):-2] 

        if tendencia == "ALCISTA" and fuerza == "FUERTE":
            # 1. Buscamos el Pico Máximo (Punto B)
            punto_b = df_impulso['high'].max()
            idx_b = df_impulso['high'].idxmax()
            
            # 2. Buscamos el Valle (Punto A) que ocurrió ANTES del Pico B
            df_previo_b = df_impulso.loc[:idx_b]
            punto_a = df_previo_b['low'].min() if not df_previo_b.empty else df_impulso['low'].min()
            
            leg_size = punto_b - punto_a
            
            if leg_size > 0:
                # 3. Calculamos la Zona Dorada de Fibonacci (38.2% al 61.8%)
                fib_38 = punto_b - (leg_size * 0.382)
                fib_61 = punto_b - (leg_size * 0.618)
                
                # 4. Verificamos la Confluencia: ¿El precio entró a la zona Fib y rebotó en la SMA20?
                toque_sma = any(v['low'] <= (v[col_sma20] + zona_pullback_atr) for _, v in velas_recientes.iterrows())
                en_zona_fib = (fib_61 - zona_pullback_atr) <= vela_actual_cerrada['low'] <= (fib_38 + zona_pullback_atr)
                
                if toque_sma and en_zona_fib and precio > vela_actual_cerrada[col_sma20]:
                    gatillo = "COMPRA (Fibonacci + SMA20)"
                    
        elif tendencia == "BAJISTA" and fuerza == "FUERTE":
            # 1. Buscamos el Valle Mínimo (Punto B)
            punto_b = df_impulso['low'].min()
            idx_b = df_impulso['low'].idxmin()
            
            # 2. Buscamos el Pico (Punto A) que ocurrió ANTES del Valle B
            df_previo_b = df_impulso.loc[:idx_b]
            punto_a = df_previo_b['high'].max() if not df_previo_b.empty else df_impulso['high'].max()
            
            leg_size = punto_a - punto_b
            
            if leg_size > 0:
                # 3. Calculamos la Zona Dorada de Fibonacci (38.2% al 61.8%)
                fib_38 = punto_b + (leg_size * 0.382)
                fib_61 = punto_b + (leg_size * 0.618)
                
                toque_sma = any(v['high'] >= (v[col_sma20] - zona_pullback_atr) for _, v in velas_recientes.iterrows())
                en_zona_fib = (fib_38 - zona_pullback_atr) <= vela_actual_cerrada['high'] <= (fib_61 + zona_pullback_atr)
                
                if toque_sma and en_zona_fib and precio < vela_actual_cerrada[col_sma20]:
                    gatillo = "VENTA (Fibonacci + SMA20)"

        diagnostico_global[simbolo] = {
            "precio": precio,
            "tendencia": tendencia,
            "estado_adx": fuerza,
            "valor_adx": round(vela_actual_cerrada[col_adx], 2),
            "gatillo_activo": gatillo
        }

    mt5.shutdown()
    return diagnostico_global

# ==========================================
# 3. TEST DE LABORATORIO
# ==========================================
if __name__ == "__main__":
    MONEDAS_PRUEBA = ["EURUSD", "GBPUSD", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD", "AUDJPY"]
    
    print(f"🌊 Iniciando Radar de Momentum (Con Fibonacci y ATR)...")
    resultados = analizar_momentum_multimoneda(MONEDAS_PRUEBA)
    
    print("\n=======================================================")
    print("   🏄‍♂️ RADIOGRAFÍA DE TENDENCIAS (TREND-FOLLOWING)")
    print("=======================================================")
    for moneda, datos in resultados.items():
        alerta = "🎯 GATILLO: " + datos['gatillo_activo'] if datos['gatillo_activo'] else "Esperando ola."
        print(f"{moneda} | Precio: {datos['precio']} | Macro: {datos['tendencia']}")
        print(f"   -> ADX (Fuerza): {datos['valor_adx']} - {datos['estado_adx']}")
        print(f"   -> Acción: {alerta}")
        print("-------------------------------------------------------")