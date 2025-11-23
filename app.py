from flask import Flask
# Importamos los Blueprints que creamos en la carpeta routes
from routes.general import general_bp
from routes.siembra_link import siembra_link_bp
from routes.siembra_bot import siembra_bot_bp
from routes.siembra_vision import siembra_vision_bp

app = Flask(__name__)

# --- REGISTRO DE BLUEPRINTS ---
# Esto conecta los archivos separados con la aplicación principal

app.register_blueprint(general_bp)
app.register_blueprint(siembra_link_bp)
app.register_blueprint(siembra_bot_bp)
app.register_blueprint(siembra_vision_bp)

if __name__ == '__main__':
    app.run(debug=True)