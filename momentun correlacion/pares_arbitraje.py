import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ==========================================
# 1. PARES A VIGILAR (La Crema del Mercado)
# ==========================================
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

MONEDAS_ACTIVAS = list(set([moneda for pareja in PARES_INVERSOS for moneda in pareja]))

# ==========================================
# 2. FUNCIONES AUXILIARES
# ==========================================
def obtener_cierres(simbolo, temporalidad, velas):
    datos = mt5.copy_rates_from_pos(simbolo, temporalidad, 0, velas)
    if datos is None: return None
    return pd.DataFrame(datos)['close']

def verificar_en_zona(precio_actual, zonas_moneda):
    for zona in zonas_moneda:
        if zona['piso'] <= precio_actual <= zona['techo']:
            return zona 
    return None

# ==========================================
# 3. MOTOR CENTRAL (TRIFECTA DE MOMENTUM)
# ==========================================
def analizar_anomalias_arbitraje(temporalidad=mt5.TIMEFRAME_H1, velas_historial=300):
    from Buscador_Zonas import obtener_zonas_mercado
    from Reversion_Media import analizar_momentum_multimoneda 
    
    todas_las_zonas = obtener_zonas_mercado()
    if not todas_las_zonas: return []

    print("📡 Escaneando Momentum (ADX/SMA) de todas las monedas...")
    momentum_global = analizar_momentum_multimoneda(MONEDAS_ACTIVAS)

    anomalias = []
    umbral_ruptura = 1.5  

    print("\n⚙️ Cruzando Spread + Zonas de Soporte + Momentum...\n")
    
    for par1, par2 in PARES_INVERSOS:
        cierres1 = obtener_cierres(par1, temporalidad, velas_historial)
        cierres2 = obtener_cierres(par2, temporalidad, velas_historial)

        if cierres1 is None or cierres2 is None: continue

        precio_par1 = cierres1.iloc[-1]
        precio_par2 = cierres2.iloc[-1]

        # A. Cálculos Estadísticos (Spread)
        z1 = (precio_par1 - cierres1.mean()) / cierres1.std()
        z2 = (precio_par2 - cierres2.mean()) / cierres2.std()
        spread = z1 + z2
        
        estado_spread = "RANGO"
        if spread > umbral_ruptura: estado_spread = "TENDENCIA ALCISTA (Spread)"
        elif spread < -umbral_ruptura: estado_spread = "TENDENCIA BAJISTA (Spread)"
        
        # B. Análisis de Zonas
        zona_p1 = verificar_en_zona(precio_par1, todas_las_zonas.get(par1, []))
        zona_p2 = verificar_en_zona(precio_par2, todas_las_zonas.get(par2, []))

        # C. Extracción de Momentum
        mom_p1 = momentum_global.get(par1, {})
        mom_p2 = momentum_global.get(par2, {})

        # D. Evaluación de la TRIFECTA
        confirmacion = "Mercado flotando o sin fuerza."
        tipo_alerta = "⚪"

        gatillo_p1 = mom_p1.get('gatillo_activo', None)
        gatillo_p2 = mom_p2.get('gatillo_activo', None)

        if "TENDENCIA" in estado_spread:
            if zona_p1 and gatillo_p1:
                tipo_alerta = "🏄‍♂️"
                confirmacion = "¡OLA PERFECTA! Tendencia Macro + Pullback en Zona K-Means."
            else:
                tipo_alerta = "🌊"
                confirmacion = "Tendencia activa, esperando pullback claro."
        
        elif gatillo_p1 or gatillo_p2:
            tipo_alerta = "👀"
            confirmacion = "Posible inicio de movimiento (Pullback detectado sin macro spread)."

        anomalias.append({
            "par1": par1, "precio1": precio_par1, "z1": z1, "en_zona1": bool(zona_p1), "mom_p1": mom_p1,
            "par2": par2, "precio2": precio_par2, "z2": z2, "en_zona2": bool(zona_p2), "mom_p2": mom_p2,
            "spread": spread, "estado_spread": estado_spread, "confirmacion": confirmacion, "icono": tipo_alerta
        })

    return anomalias

# ==========================================
# 4. TEST DE LABORATORIO
# ==========================================
if __name__ == "__main__":
    print("🚀 INICIANDO RADAR DE TREND-FOLLOWING...")
    
    # 🔥 ABRIMOS LA PUERTA UNA SOLA VEZ AQUÍ
    if not mt5.initialize():
        print("❌ Error crítico: No se pudo conectar a MT5")
        quit()
        
    resultados = analizar_anomalias_arbitraje()
    
    print("=======================================================")
    print("   📊 TABLERO DE CONTROL: MOMENTUM Y PULLBACKS")
    print("=======================================================")
    for r in resultados:
        p1_info = r['mom_p1']
        p2_info = r['mom_p2']
        
        print(f"{r['icono']} {r['par1']} vs {r['par2']} | Spread: {r['spread']:.2f} ({r['estado_spread']})")
        
        # Fila Par 1
        zona1_txt = "SÍ 🧱" if r['en_zona1'] else "NO 💨"
        gatillo1_txt = f" | 🎯 {p1_info.get('gatillo_activo')}" if p1_info.get('gatillo_activo') else ""
        adx1 = p1_info.get('valor_adx', 'N/A')
        print(f"   -> {r['par1']} [Z: {r['z1']:.2f}] | Zona: {zona1_txt} | ADX: {adx1} {gatillo1_txt}")
        
        # Fila Par 2
        zona2_txt = "SÍ 🧱" if r['en_zona2'] else "NO 💨"
        gatillo2_txt = f" | 🎯 {p2_info.get('gatillo_activo')}" if p2_info.get('gatillo_activo') else ""
        adx2 = p2_info.get('valor_adx', 'N/A')
        print(f"   -> {r['par2']} [Z: {r['z2']:.2f}] | Zona: {zona2_txt} | ADX: {adx2} {gatillo2_txt}")
        
        # Conclusión
        print(f"   -> Veredicto: {r['confirmacion']}")
        print("-------------------------------------------------------")
        
    # 🔥 CERRAMOS LA PUERTA UNA SOLA VEZ AL TERMINAR
    mt5.shutdown()