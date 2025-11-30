import threading
import sys
import os
from flask import Blueprint, render_template, jsonify
from datetime import datetime

# Ajuste de path para importar lógica
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.append(project_root)

# Importamos la lógica consolidada del Agente
from logic.agente_voz import ejecutar_agente
# Importamos catálogos para llenar los <select> del HTML
from logic.catalogos import estados, municipios, coordenadas

base_bp = Blueprint('base', __name__)

# --- RUTA 1: PÁGINA DE INICIO ---
@base_bp.route('/')
def index():
    # Datos necesarios para que index.html no falle
    meses = ("Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre")
    anio_actual = datetime.now().year
    mes_actual = meses[datetime.now().month - 1]

    context = {
        "title": "Inicio",
        "mes_sel": mes_actual, 
        "anio_sel": anio_actual, 
        "recomendaciones": [],
        "estados": estados, 
        "municipios": municipios, 
        "meses": meses, 
        "anios": [anio_actual],
        # Valores por defecto para evitar errores jinja2
        "temp_max": None, "temp_min": None, "precipitacion": None, 
        "humedad": None, "nombre_mes": None,
        "latitud_mapa": 19.1738, "longitud_mapa": -96.1342
    }
    # Renderizamos index.html que extiende de base.html
    return render_template('index.html', **context)

# --- RUTA 2: API DE VOZ (Llamada por el botón flotante) ---
@base_bp.route('/api/activar-voz', methods=['POST'])
def activar_voz():
    """Lanza el agente en segundo plano"""
    try:
        # Usamos threading para no congelar la página web mientras el bot escucha
        hilo = threading.Thread(target=ejecutar_agente)
        hilo.start()
        return jsonify({"status": "success", "message": "Agente escuchando..."}), 200
    except Exception as e:
        print(f"Error activando voz: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500