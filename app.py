import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from routes.general import general_bp
from routes.siembra_link import siembra_link_bp
from routes.siembra_bot import siembra_bot_bp
from routes.siembra_vision import siembra_vision_bp
from routes.base import base_bp
from routes.auth_snap import auth_snap_bp
from routes.siembra_snap import siembra_snap_bp

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'sm-dev-fallback-key-change-in-prod')

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(general_bp)
app.register_blueprint(siembra_link_bp)
app.register_blueprint(siembra_bot_bp)
app.register_blueprint(siembra_vision_bp)
app.register_blueprint(base_bp)
app.register_blueprint(auth_snap_bp)
app.register_blueprint(siembra_snap_bp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)