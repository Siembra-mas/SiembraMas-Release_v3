import sys
import os
import uuid
from flask import Blueprint, render_template, jsonify, request, url_for, current_app

# --- NUEVO IMPORT: Usamos el cerebro centralizado ---
from logic.cerebro_bot import consultar_cerebro, transcribir_audio_groq, generar_audio_respuesta

base_bp = Blueprint('base', __name__)

# --- API DEL CHAT FLOTANTE (GLOBAL) ---

@base_bp.route('/api/widget-chat', methods=['POST'])
def api_widget_chat():
    """
    Endpoint del widget flotante. Acepta FormData igual que SiembraBot:
    - 'mensaje'    (str)  texto del usuario
    - 'audio_blob' (file) grabación de voz
    - 'lat', 'lon' (opt)  coordenadas
    Devuelve { bot, audio_url } con la misma estructura que SiembraBot.
    """
    datos        = request.form
    archivo_audio = request.files.get('audio_blob')

    texto_usuario = datos.get('mensaje', '')
    lat = datos.get('lat')
    lon = datos.get('lon')

    # Si llega audio, transcribirlo primero (mismo flujo que SiembraBot)
    if archivo_audio:
        temp_filename = f"temp_{uuid.uuid4().hex}.wav"
        temp_path = os.path.join(current_app.static_folder, 'temp', temp_filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        archivo_audio.save(temp_path)
        transcripcion = transcribir_audio_groq(temp_path)
        try:
            os.remove(temp_path)
        except:
            pass
        if not transcripcion:
            return jsonify({"error": "No se pudo escuchar el audio"}), 400
        texto_usuario = transcripcion

    if not texto_usuario:
        return jsonify({"error": "Mensaje vacío"}), 400

    respuesta_texto = consultar_cerebro(texto_usuario, [], lat, lon)
    audio_url = generar_audio_respuesta(respuesta_texto, current_app.static_folder)

    return jsonify({
        "usuario": texto_usuario,
        "bot": respuesta_texto,
        "audio_url": audio_url   # ruta relativa, ej: "audio/resp_xxx.mp3"
    })