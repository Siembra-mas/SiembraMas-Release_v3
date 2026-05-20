# Ubicación: routes/siembra_vision.py
from flask import Blueprint, render_template, request, jsonify
from PIL import Image
import io

# Importamos la función de lógica que creamos arriba
# Ajusta la importación según tu estructura de carpetas
try:
    from logic.vision_logic import procesar_prediccion
except ImportError:
    def procesar_prediccion(img_pil):
        return {"error": "Módulo de visión no disponible.", "diagnostico": "No disponible", "descripcion": "", "id": -1, "status": "unavailable"}

siembra_vision_bp = Blueprint('siembra_vision', __name__)

@siembra_vision_bp.route('/siembra-vision', methods=['GET'])
def index():
    return render_template('siembra_vision.html', title="Siembra Visión")

@siembra_vision_bp.route('/siembra-vision/analizar', methods=['POST'])
def analizar_imagen():
    """
    Endpoint API que recibe una imagen y devuelve JSON con el diagnóstico.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ninguna imagen'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400

    try:
        # Convertir bytes a imagen PIL
        image_bytes = file.read()
        img_pil = Image.open(io.BytesIO(image_bytes))
        
        # Llamar a la lógica de IA
        resultado = procesar_prediccion(img_pil)
        
        return jsonify({
            'success': True,
            'data': resultado
        })
        
    except Exception as e:
        print(f"Error en servidor: {e}")
        return jsonify({'error': str(e)}), 500