from flask import Blueprint, render_template

# Creamos el Blueprint
general_bp = Blueprint('general', __name__)

@general_bp.route('/')
def index():
    # Aquí podrías cargar datos iniciales globales si fuera necesario
    return render_template('index.html', title="Inicio")

@general_bp.route('/precios')
def precios():
    return render_template('precios.html', title="Planes y Precios")

@general_bp.route('/nosotros')
def about():
    return render_template('about.html', title="Sobre Nosotros")

@general_bp.route('/privacidad')
def privacidad():
    return render_template('privacy.html', title="Aviso de Privacidad")

@general_bp.route('/terminos')
def terminos():
    return render_template('privacy.html', title="Términos de Uso")