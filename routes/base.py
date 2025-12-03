import sys
import os
import uuid
from flask import Blueprint, render_template, jsonify, request, url_for, current_app

# --- NUEVO IMPORT: Usamos el cerebro centralizado ---
from logic.cerebro_bot import consultar_cerebro, transcribir_audio_groq, generar_audio_respuesta

base_bp = Blueprint('base', __name__)

@base_bp.route('/')
def index():
    context = {
        "title": "Inicio",
        # ... tus otros datos ...
    }
    return render_template('index.html', **context)

# --- API DEL CHAT FLOTANTE (GLOBAL) ---

@base_bp.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Maneja mensajes de TEXTO enviados desde el widget flotante.
    """
    data = request.json
    mensaje = data.get('mensaje')
    historial = data.get('historial', []) 
    
    # Intentamos obtener ubicación si el JS la envía (opcional)
    lat = data.get('lat')
    lon = data.get('lon')
    
    if not mensaje:
        return jsonify({"error": "Mensaje vacío"}), 400

    # 1. Consultar cerebro (Lógica centralizada)
    respuesta_texto = consultar_cerebro(mensaje, historial, lat, lon)
    
    # 2. Generar Audio de la respuesta
    # Usamos current_app.static_folder para asegurar la ruta correcta en cualquier OS
    audio_url = generar_audio_respuesta(respuesta_texto, current_app.static_folder)
    
    # Ajustamos la URL para que sea accesible desde el navegador
    # generar_audio_respuesta devuelve algo como "audio/archivo.mp3"
    full_audio_url = url_for('static', filename=audio_url) if audio_url else None

    return jsonify({
        "respuesta": respuesta_texto,
        "audio_url": full_audio_url
    })

@base_bp.route('/api/audio-upload', methods=['POST'])
def api_audio_upload():
    """
    Maneja grabación de AUDIO (micrófono) desde el widget flotante.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
        
    audio_file = request.files['audio']
    
    # Intentamos obtener ubicación del form data si el JS la envía
    lat = request.form.get('lat')
    lon = request.form.get('lon')
    
    # Guardar temporalmente el audio del usuario
    filename = f"input_{uuid.uuid4().hex}.wav"
    temp_path = os.path.join(current_app.static_folder, 'temp', filename)
    
    # Asegurar que existe la carpeta temp
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    audio_file.save(temp_path)
    
    # 1. Transcribir con Groq (Igual que en SiembraBot)
    texto_usuario = transcribir_audio_groq(temp_path)
    
    # Limpieza: Borrar el audio de entrada para no llenar el servidor
    try:
        os.remove(temp_path)
    except:
        pass
    
    if not texto_usuario:
        return jsonify({"respuesta": "No pude escuchar bien, intenta de nuevo.", "transcripcion": ""})

    # 2. Consultar Cerebro
    respuesta_texto = consultar_cerebro(texto_usuario, [], lat, lon)
    
    # 3. Generar Audio Respuesta
    audio_url_rel = generar_audio_respuesta(respuesta_texto, current_app.static_folder)
    full_audio_url = url_for('static', filename=audio_url_rel) if audio_url_rel else None

    return jsonify({
        "transcripcion": texto_usuario,
        "respuesta": respuesta_texto,
        "audio_url": full_audio_url
    })