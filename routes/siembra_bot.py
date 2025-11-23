from flask import Blueprint, render_template

siembra_bot_bp = Blueprint('siembra_bot', __name__)

@siembra_bot_bp.route('/siembra-bot')
def index():
    # LÓGICA ESPECÍFICA:
    # Aquí podrías inicializar el contexto de la IA o cargar historial de chat.
    return render_template('siembra_bot.html', title="Siembra Bot (IA)")