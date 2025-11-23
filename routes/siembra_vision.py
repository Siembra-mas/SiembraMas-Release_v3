from flask import Blueprint, render_template

siembra_vision_bp = Blueprint('siembra_vision', __name__)

@siembra_vision_bp.route('/siembra-vision')
def index():
    # LÓGICA ESPECÍFICA:
    # Aquí configurarías la carga de imágenes o el stream de video.
    return render_template('siembra_vision.html', title="Siembra Visión")