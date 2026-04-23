import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta

# ==========================================
# 1. PARÁMETROS DEL SENSOR
# ==========================================
TEMPORALIDAD = mt5.TIMEFRAME_H1 
VELAS_HISTORIAL = 250 

# Parámetros Matemáticos
SMA_PERIOD = 200
BB_PERIOD = 20
BB_STD = 2.0
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# ==========================================
# 2. MOTOR DE ANÁLISIS DE MOMENTUM
# ==========================================
def analizar_momentum_multimoneda(lista_monedas):
    """
    Escanea una lista de monedas y devuelve su estado de tendencia,
    anomalías de Bollinger y gatillos de RSI en un diccionario.
    """
    if not mt5.initialize():
        print("Error al inicializar MT5 en Reversion_Media")
        return {}

    diagnostico_global = {}

    for simbolo in lista_monedas:
        velas = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD, 0, VELAS_HISTORIAL)
        
        # Filtro de seguridad por si una moneda no tiene historial suficiente
        if velas is None or len(velas) < SMA_PERIOD:
            continue

        df = pd.DataFrame(velas)
        df.ta.sma(length=SMA_PERIOD, append=True)
        df.ta.bbands(length=BB_PERIOD, std=BB_STD, append=True)
        df.ta.rsi(length=RSI_PERIOD, append=True)
        df.dropna(inplace=True)

        if df.empty: continue

        col_sma = [c for c in df.columns if c.startswith('SMA')][0]
        col_bbl = [c for c in df.columns if c.startswith('BBL')][0] 
        col_bbu = [c for c in df.columns if c.startswith('BBU')][0] 
        col_rsi = [c for c in df.columns if c.startswith('RSI')][0]

        vela_actual = df.iloc[-2]
        vela_anterior = df.iloc[-3]
        precio = vela_actual['close']

        # --- LÓGICA DE DIAGNÓSTICO ---
        tendencia = "ALCISTA" if precio > vela_actual[col_sma] else "BAJISTA"
        
        estado_bb = "CONCENTRADO"
        if precio <= vela_actual[col_bbl]: estado_bb = "PÁNICO (Piso BB)"
        elif precio >= vela_actual[col_bbu]: estado_bb = "EUFORIA (Techo BB)"

        gatillo = None
        
        # Evaluar Gatillos de Reversión
        if tendencia == "ALCISTA":
            if vela_actual['low'] <= vela_actual[col_bbl] or vela_anterior['low'] <= vela_anterior[col_bbl]: 
                if vela_anterior[col_rsi] < RSI_OVERSOLD and vela_actual[col_rsi] >= RSI_OVERSOLD: 
                    gatillo = "COMPRA"
        
        elif tendencia == "BAJISTA":
            if vela_actual['high'] >= vela_actual[col_bbu] or vela_anterior['high'] >= vela_anterior[col_bbu]: 
                if vela_anterior[col_rsi] > RSI_OVERBOUGHT and vela_actual[col_rsi] <= RSI_OVERBOUGHT: 
                    gatillo = "VENTA"

        # Empaquetar la información
        diagnostico_global[simbolo] = {
            "precio": precio,
            "tendencia": tendencia,
            "rsi": round(vela_actual[col_rsi], 2),
            "estado_bb": estado_bb,
            "gatillo_activo": gatillo
        }

    mt5.shutdown()
    return diagnostico_global

# ==========================================
# 3. TEST DE LABORATORIO
# ==========================================
if __name__ == "__main__":
    # Importamos la lista dinámica para hacer la prueba
    from pares_arbitraje import MONEDAS_ACTIVAS
    
    print(f"📡 Iniciando escáner de Momentum para {len(MONEDAS_ACTIVAS)} monedas...")
    resultados = analizar_momentum_multimoneda(MONEDAS_ACTIVAS)
    
    print("\n=======================================================")
    print("   📉 RADIOGRAFÍA DE MOMENTUM")
    print("=======================================================")
    for moneda, datos in resultados.items():
        alerta = "🚨 GATILLO: " + datos['gatillo_activo'] if datos['gatillo_activo'] else "Esperando."
        print(f"{moneda} | Precio: {datos['precio']} | Tendencia: {datos['tendencia']}")
        print(f"   -> Bollinger: {datos['estado_bb']} | RSI: {datos['rsi']}")
        print(f"   -> Acción: {alerta}")
        print("-------------------------------------------------------")