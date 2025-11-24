from flask import Blueprint, render_template
import pandas as pd
import json
import os

siembra_link_bp = Blueprint('siembra_link', __name__)

def cargar_datos_csv():
    """
    Carga los CSVs de Germinación, Floración y Maduración.
    Estructura los datos para enviarlos al Frontend.
    """
    # Mapeo de Etapa (Select HTML) -> Nombre del Archivo
    archivos = {
        "1": "data/fase_cultivo/Germinacion_procesado.csv",
        "2": "data/fase_cultivo/Floracion_procesado.csv",
        "3": "data/fase_cultivo/Maduracion_procesado.csv"
    }
    
    base_datos = {}

    for etapa_id, archivo in archivos.items():
        try:
            # Leemos el CSV
            df = pd.read_csv(archivo)
            base_datos[etapa_id] = {}
            
            for index, row in df.iterrows():
                cultivo = row['Cultivo']
                
                # Guardamos Mínimo, Máximo y PROMEDIO para cada variable
                base_datos[etapa_id][cultivo] = {
                    # Temperatura
                    "temp_min": row.get('Temp. Recomendada (°C)_valor_mínimo', 0),
                    "temp_max": row.get('Temp. Recomendada (°C)_valor_máximo', 0),
                    "temp_prom": row.get('Temp. Recomendada (°C)_valor_promedio', 0),
                    
                    # Humedad Suelo
                    "hum_suelo_min": row.get('Humedad Suelo (%)_valor_mínimo', 0),
                    "hum_suelo_max": row.get('Humedad Suelo (%)_valor_máximo', 0),
                    "hum_suelo_prom": row.get('Humedad Suelo (%)_valor_promedio', 0),
                    
                    # Precipitación (Lluvia)
                    "lluvia_min": row.get('Lluvia Óptima (mm)_valor_mínimo', 0),
                    "lluvia_max": row.get('Lluvia Óptima (mm)_valor_máximo', 0),
                    "lluvia_prom": row.get('Lluvia Óptima (mm)_valor_promedio', 0)
                }
        except Exception as e:
            print(f"⚠️ Error cargando {archivo}: {e}")
            
    return base_datos

@siembra_link_bp.route('/siembra-link')
def index():
    # 1. Cargar base de conocimientos
    datos_cultivos = cargar_datos_csv()
    
    # 2. Obtener lista de cultivos para llenar el Select (usamos etapa 1 como referencia)
    lista_cultivos = sorted(list(datos_cultivos.get("1", {}).keys())) if datos_cultivos else []

    # 3. DATOS SIMULADOS DEL SENSOR (Esto vendrá de tu Arduino 'monitoreo.py' después)
    # Aquí simulamos valores actuales para probar la visualización
    datos_sensor_actual = {
        "temp": 26,           # °C
        "humedad_suelo": 48,  # %
        "lluvia": 650         # mm
    }
    
    # Convertimos a JSON string para que JS lo pueda leer
    db_json = json.dumps(datos_cultivos)
    
    return render_template('siembra_link.html', 
                           title="Siembra Link (IoT)", 
                           datos_sensor=datos_sensor_actual,
                           db_cultivos=db_json,
                           lista_cultivos=lista_cultivos)