from flask import Blueprint, render_template

siembra_link_bp = Blueprint('siembra_link', __name__)

@siembra_link_bp.route('/siembra-link')
def index():
    # LÓGICA ESPECÍFICA:
    # Aquí conectarás con Firebase o tu API de Arduino en el futuro.
    datos_sensor = { "humedad": "Calculando...", "temp": "---" } # Ejemplo
    
    return render_template('siembra_link.html', title="Siembra Link (IoT)", datos=datos_sensor)