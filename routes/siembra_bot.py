import os
from flask import Blueprint, render_template, request, jsonify, current_app
from logic.cerebro_bot import consultar_cerebro, transcribir_audio_groq, generar_audio_respuesta
import uuid

siembra_bot_bp = Blueprint('siembra_bot', __name__)

@siembra_bot_bp.route('/siembra-bot')
def index():
    return render_template('siembra_bot.html', title="Siembra Bot (IA)")

@siembra_bot_bp.route('/api/chat', methods=['POST'])
def chat_api():
    """Endpoint único para texto y audio"""
    datos = request.form
    archivo_audio = request.files.get('audio_blob')
    
    texto_usuario = datos.get('mensaje', '')
    lat = datos.get('lat')
    lon = datos.get('lon')
    historial = [] # En producción, recibirías esto del JSON del frontend

    # 1. Si llega audio, transcribirlo primero
    if archivo_audio:
        # Guardar temporalmente
        temp_filename = f"temp_{uuid.uuid4().hex}.wav"
        temp_path = os.path.join(current_app.static_folder, 'temp', temp_filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        archivo_audio.save(temp_path)
        
        # Transcribir con Groq
        transcripcion = transcribir_audio_groq(temp_path)
        
        # Limpiar archivo temp
        try: os.remove(temp_path)
        except: pass
        
        if not transcripcion:
            return jsonify({"error": "No se pudo escuchar el audio"}), 400
        texto_usuario = transcripcion

    if not texto_usuario:
        return jsonify({"error": "Mensaje vacío"}), 400

    # 2. Consultar al Cerebro (LLM)
    respuesta_texto = consultar_cerebro(texto_usuario, historial, lat, lon)

    # 3. Generar Audio de Respuesta
    url_audio = generar_audio_respuesta(respuesta_texto, current_app.static_folder)

    return jsonify({
        "usuario": texto_usuario,
        "bot": respuesta_texto,
        "audio_url": url_audio
    })