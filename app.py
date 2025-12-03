from flask import Flask
from routes.general import general_bp
from routes.siembra_link import siembra_link_bp
from routes.siembra_bot import siembra_bot_bp
from routes.siembra_vision import siembra_vision_bp
from routes.base import base_bp  # NUEVO: Importamos el router base

app = Flask(__name__)

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(general_bp)
app.register_blueprint(siembra_link_bp)
app.register_blueprint(siembra_bot_bp)
app.register_blueprint(siembra_vision_bp)
app.register_blueprint(base_bp)  # NUEVO: Registramos el router base

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)