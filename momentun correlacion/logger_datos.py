import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "dataset_arbitraje.db"

def inicializar_db():
    """Crea la base de datos y la tabla si no existen."""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # Creamos la tabla con todas las "Features" (Características) que la IA necesitará aprender
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS registro_mercado (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        par1 TEXT,
        par2 TEXT,
        precio1 REAL,
        precio2 REAL,
        z_score1 REAL,
        z_score2 REAL,
        spread REAL,
        en_zona1 BOOLEAN,
        en_zona2 BOOLEAN,
        rsi1 REAL,
        rsi2 REAL,
        tendencia1 TEXT,
        tendencia2 TEXT,
        estado_spread TEXT,
        icono_alerta TEXT
    )
    ''')
    conexion.commit()
    conexion.close()

def guardar_fotografia_mercado(resultados_trifecta):
    """Recibe la lista de resultados de pares_arbitraje y la guarda en la DB."""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%00")
    
    for r in resultados_trifecta:
        # Extraemos los datos de los diccionarios anidados
        mom_p1 = r.get('mom_p1', {})
        mom_p2 = r.get('mom_p2', {})
        
        cursor.execute('''
        INSERT INTO registro_mercado (
            timestamp, par1, par2, precio1, precio2, z_score1, z_score2, 
            spread, en_zona1, en_zona2, rsi1, rsi2, tendencia1, tendencia2, 
            estado_spread, icono_alerta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 
            r['par1'], r['par2'], 
            r['precio1'], r['precio2'], 
            r['z1'], r['z2'], 
            r['spread'], 
            r['en_zona1'], r['en_zona2'],
            mom_p1.get('rsi', 50.0), mom_p2.get('rsi', 50.0),
            mom_p1.get('tendencia', 'NEUTRAL'), mom_p2.get('tendencia', 'NEUTRAL'),
            r['estado_spread'], r['icono']
        ))
        
    conexion.commit()
    conexion.close()

# Inicializamos la DB la primera vez que se lee este archivo
inicializar_db()

# Si ejecutas este archivo directo, puedes ver qué datos has recolectado
if __name__ == "__main__":
    try:
        conexion = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM registro_mercado", conexion)
        print(f"📦 Base de datos activa. Total de registros: {len(df)}")
        if not df.empty:
            print(df.tail(5)) # Muestra los últimos 5 registros
        conexion.close()
    except Exception as e:
        print("La base de datos aún está vacía o no existe.")