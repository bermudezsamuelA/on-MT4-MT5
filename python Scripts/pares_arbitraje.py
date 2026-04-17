import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ==========================================
# 1. PARES A VIGILAR
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
# 2. MOTOR DE SPREAD + VERIFICACIÓN DE ZONAS
# ==========================================
def obtener_cierres(simbolo, temporalidad, velas):
    datos = mt5.copy_rates_from_pos(simbolo, temporalidad, 0, velas)
    if datos is None: return None
    return pd.DataFrame(datos)['close']

def verificar_en_zona(precio_actual, zonas_moneda):
    """Devuelve la zona si el precio está dentro de ella"""
    for zona in zonas_moneda:
        if zona['piso'] <= precio_actual <= zona['techo']:
            return zona 
    return None

def analizar_anomalias_arbitraje(temporalidad=mt5.TIMEFRAME_H1, velas_historial=250):
    from Buscador_Zonas import obtener_zonas_mercado
    
    todas_las_zonas = obtener_zonas_mercado()
    if not todas_las_zonas: return []

    if not mt5.initialize(): return []

    anomalias = []
    umbral_ruptura = 2.0  

    print("\n⚙️ Cruzando datos estadísticos (Spread) con Cajas Rojas (K-Means)...")
    
    for par1, par2 in PARES_INVERSOS:
        cierres1 = obtener_cierres(par1, temporalidad, velas_historial)
        cierres2 = obtener_cierres(par2, temporalidad, velas_historial)

        if cierres1 is None or cierres2 is None: continue

        precio_par1 = cierres1.iloc[-1]
        precio_par2 = cierres2.iloc[-1]

        z1 = (precio_par1 - cierres1.mean()) / cierres1.std()
        z2 = (precio_par2 - cierres2.mean()) / cierres2.std()
        spread = z1 + z2
        
        estado = "EQUILIBRIO"
        if spread > umbral_ruptura: estado = "LEJOS_ARRIBA"
        elif spread < -umbral_ruptura: estado = "LEJOS_ABAJO"
        
        zona_p1 = verificar_en_zona(precio_par1, todas_las_zonas.get(par1, []))
        zona_p2 = verificar_en_zona(precio_par2, todas_las_zonas.get(par2, []))

        # NUEVA LÓGICA DE DIAGNÓSTICO (Basada en tus imágenes)
        confirmacion = "Mercado flotando, sin oportunidades claras."
        tipo_alerta = "⚪"

        # Escenario 1: Falla en la Matrix (Descorrelación)
        if "LEJOS" in estado:
            tipo_alerta = "🚨"
            confirmacion = "FALLA EN LA MATRIX: Spread anormal."
            if zona_p1 or zona_p2:
                confirmacion += " + Apoyo en Zonas. ¡Oportunidad de Convergencia!"

        # Escenario 2: Doble Choque de Cajas (Tu descubrimiento)
        elif zona_p1 and zona_p2:
            tipo_alerta = "🔥"
            confirmacion = "DOBLE CHOQUE: Ambos espejos golpearon sus Zonas. ¡Gatillo de Rebote!"

        # Escenario 3: Solo uno choca
        elif zona_p1 or zona_p2:
            tipo_alerta = "👀"
            confirmacion = "Un par chocó con su Zona. Vigilando al otro..."

        anomalias.append({
            "par1": par1, "precio1": precio_par1, "en_zona1": bool(zona_p1), "z1": z1,
            "par2": par2, "precio2": precio_par2, "en_zona2": bool(zona_p2), "z2": z2,
            "spread": spread,
            "estado": estado,
            "confirmacion": confirmacion,
            "icono": tipo_alerta
        })

    mt5.shutdown()
    return anomalias

# ==========================================
# 3. TEST DE LABORATORIO
# ==========================================
if __name__ == "__main__":
    print("Iniciando Motor de Arbitraje Institucional...\n")
    resultados = analizar_anomalias_arbitraje()
    
    print("\n=======================================================")
    print("   📊 REPORTE DE ARBITRAJE ESTADÍSTICO + ZONAS")
    print("=======================================================")
    for r in resultados:
        # AHORA IMPRIME ABSOLUTAMENTE TODOS LOS PARES
        print(f"{r['icono']} {r['par1']} vs {r['par2']} | Spread: {r['spread']:.2f} ({r['estado']})")
        print(f"   -> {r['par1']} [Z-Score: {r['z1']:.2f}] | En Zona: {'SÍ 🧱' if r['en_zona1'] else 'NO 💨'}")
        print(f"   -> {r['par2']} [Z-Score: {r['z2']:.2f}] | En Zona: {'SÍ 🧱' if r['en_zona2'] else 'NO 💨'}")
        print(f"   -> Veredicto: {r['confirmacion']}")
        print("-------------------------------------------------------")