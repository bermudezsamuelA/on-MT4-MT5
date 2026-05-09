import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta

# ==========================================
# CONFIGURACIÓN DEL SEMÁFORO (MODO MACRO)
# ==========================================
TEMPORALIDAD_MACRO = mt5.TIMEFRAME_D1  # Miramos el bosque, no los árboles
VELAS_HISTORIAL = 50

# Umbrales Institucionales
UMBRAL_ADX_TENDENCIA = 25  # Por encima de 25 hay una tendencia clara
UMBRAL_VOLATILIDAD_ALTA = 1.5 # Multiplicador de ATR para detectar picos

def consultar_semaforo(simbolo):
    """
    Analiza el régimen de mercado y decide qué estrategia tiene luz verde.
    """
    if not mt5.initialize():
        return {"simbolo": simbolo, "estado": "ERROR_CONEXION", "icono": "⚪", "adx": 0, "atr_ratio": 0}

    # 1. Extraer data diaria
    velas = mt5.copy_rates_from_pos(simbolo, TEMPORALIDAD_MACRO, 0, VELAS_HISTORIAL)
    if velas is None or len(velas) < 30:
        return {"simbolo": simbolo, "estado": "SIN_DATOS", "icono": "⚪", "adx": 0, "atr_ratio": 0}

    df = pd.DataFrame(velas)
    
    # 2. Indicadores de Régimen
    # ADX: Mide la FUERZA de la tendencia (no la dirección)
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    adx_actual = adx_df['ADX_14'].iloc[-1]
    
    # ATR: Mide la volatilidad actual vs la histórica
    df.ta.atr(length=14, append=True)
    atr_actual = df['ATRr_14'].iloc[-1]
    atr_medio = df['ATRr_14'].rolling(20).mean().iloc[-1]
    
    # 3. LÓGICA DE CLASIFICACIÓN (El Veredicto)
    
    # CASO A: TENDENCIA EXPLOSIVA (Peligro para Reversión)
    if adx_actual > UMBRAL_ADX_TENDENCIA and atr_actual > (atr_medio * UMBRAL_VOLATILIDAD_ALTA):
        estado = "TENDENCIA_SALVAJE"
        color = "🔴"
        recomendacion = "APAGAR TODO. Riesgo de rompimiento masivo."
    
    elif adx_actual > UMBRAL_ADX_TENDENCIA:
        estado = "TENDENCIA_SÓLIDA"
        color = "🟡"
        recomendacion = "Encender Fakeout Classifier. Apagar Reversión a la Media."
        
    # CASO B: MERCADO LATERAL / RANGO (El paraíso de nuestros bots)
    elif adx_actual <= UMBRAL_ADX_TENDENCIA:
        estado = "RANGO_LATERAL"
        color = "🟢"
        recomendacion = "LUZ VERDE. Encender Reversión a la Media y Fakeout."
        
    else:
        estado = "INDEFINIDO"
        color = "⚪"
        recomendacion = "Esperar confirmación de régimen."

    return {
        "simbolo": simbolo,
        "estado": estado,
        "icono": color,
        "adx": round(adx_actual, 2),
        "atr_ratio": round(atr_actual / atr_medio, 2),
        "recomendacion": recomendacion
    }

# Test de Laboratorio
if __name__ == "__main__":
    monedas_test = ["EURUSD", "GBPUSD", "USDCAD"]
    print("🚦 ESCANEANDO SEMÁFORO DE RÉGIMEN DIARIO...")
    print("====================================================")
    for m in monedas_test:
        res = consultar_semaforo(m)
        print(f"{res['icono']} {res['simbolo']}: {res['estado']}")
        print(f"   -> ADX: {res['adx']} | Volatilidad: {res['atr_ratio']}x")
        print(f"   -> Acción: {res['recomendacion']}")
        print("----------------------------------------------------")