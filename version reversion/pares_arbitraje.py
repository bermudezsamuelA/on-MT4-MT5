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
# 3. MOTOR CENTRAL (TRIFECTA)
# ==========================================
def analizar_anomalias_arbitraje(temporalidad=mt5.TIMEFRAME_H1, velas_historial=250):
    # Importaciones de nuestros módulos especializados
    from Buscador_Zonas import obtener_zonas_mercado
    from Reversion_Media import analizar_momentum_multimoneda
    
    # 1. Recolectar datos de los módulos externos
    todas_las_zonas = obtener_zonas_mercado()
    if not todas_las_zonas: return []

    print("📡 Escaneando Momentum (RSI/Bollinger) de todas las monedas...")
    momentum_global = analizar_momentum_multimoneda(MONEDAS_ACTIVAS)

    if not mt5.initialize(): return []

    anomalias = []
    umbral_ruptura = 2.0  

    print("\n⚙️ Cruzando Spread + Zonas K-Means + Momentum...\n")
    
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
        
        estado_spread = "EQUILIBRIO"
        if spread > umbral_ruptura: estado_spread = "LEJOS_ARRIBA"
        elif spread < -umbral_ruptura: estado_spread = "LEJOS_ABAJO"
        
        # B. Análisis de Zonas
        zona_p1 = verificar_en_zona(precio_par1, todas_las_zonas.get(par1, []))
        zona_p2 = verificar_en_zona(precio_par2, todas_las_zonas.get(par2, []))

        # C. Extracción de Momentum
        mom_p1 = momentum_global.get(par1, {})
        mom_p2 = momentum_global.get(par2, {})

        # D. Evaluación de la TRIFECTA
        confirmacion = "Mercado flotando o señales mixtas."
        tipo_alerta = "⚪"

        # Gatillos de Momentum (¿Hay señal de compra/venta según RSI/BB?)
        gatillo_p1 = mom_p1.get('gatillo_activo', None)
        gatillo_p2 = mom_p2.get('gatillo_activo', None)

        if "LEJOS" in estado_spread:
            if zona_p1 and zona_p2 and gatillo_p1 and gatillo_p2:
                tipo_alerta = "💎"
                confirmacion = "¡TRIFECTA PERFECTA! Spread Roto + Doble Zona + Doble Gatillo Momentum."
            elif zona_p1 and zona_p2:
                tipo_alerta = "🔥"
                confirmacion = "DOBLE CHOQUE ESTRUCTURAL: Falla en spread y chocando contra zonas."
            else:
                tipo_alerta = "🚨"
                confirmacion = "FALLA EN MATRIX: Spread anormal, pero sin apoyo estructural sólido."
        
        elif zona_p1 and zona_p2:
            tipo_alerta = "⚡"
            confirmacion = "ESPEJO PERFECTO: Spread en equilibrio, pero chocando zonas al mismo tiempo."

        elif gatillo_p1 or gatillo_p2:
            tipo_alerta = "👀"
            confirmacion = "Señal de momentum aislada detectada. Sin confirmación estructural."

        anomalias.append({
            "par1": par1, "precio1": precio_par1, "z1": z1, "en_zona1": bool(zona_p1), "mom_p1": mom_p1,
            "par2": par2, "precio2": precio_par2, "z2": z2, "en_zona2": bool(zona_p2), "mom_p2": mom_p2,
            "spread": spread, "estado_spread": estado_spread, "confirmacion": confirmacion, "icono": tipo_alerta
        })

    mt5.shutdown()
    return anomalias

# ==========================================
# 4. TEST DE LABORATORIO
# ==========================================
if __name__ == "__main__":
    print("🚀 INICIANDO SCRIPT DE SEÑALES MULTIDIMENSIONAL...")
    resultados = analizar_anomalias_arbitraje()
    
    print("=======================================================")
    print("   📊 TABLERO DE CONTROL: ARBITRAJE ESTADÍSTICO")
    print("=======================================================")
    for r in resultados:
        # Extraemos info para lectura rápida
        p1_info = r['mom_p1']
        p2_info = r['mom_p2']
        
        print(f"{r['icono']} {r['par1']} vs {r['par2']} | Spread: {r['spread']:.2f} ({r['estado_spread']})")
        
        # Fila Par 1
        zona1_txt = "SÍ 🧱" if r['en_zona1'] else "NO 💨"
        gatillo1_txt = f" | Gatillo: {p1_info.get('gatillo_activo')}" if p1_info.get('gatillo_activo') else ""
        print(f"   -> {r['par1']} [Z: {r['z1']:.2f}] | Zona: {zona1_txt} | RSI: {p1_info.get('rsi')}{gatillo1_txt}")
        
        # Fila Par 2
        zona2_txt = "SÍ 🧱" if r['en_zona2'] else "NO 💨"
        gatillo2_txt = f" | Gatillo: {p2_info.get('gatillo_activo')}" if p2_info.get('gatillo_activo') else ""
        print(f"   -> {r['par2']} [Z: {r['z2']:.2f}] | Zona: {zona2_txt} | RSI: {p2_info.get('rsi')}{gatillo2_txt}")
        
        # Conclusión
        print(f"   -> Veredicto: {r['confirmacion']}")
        print("-------------------------------------------------------")