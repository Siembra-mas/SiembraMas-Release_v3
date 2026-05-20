from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
import os
import base64
import json

auth_snap_bp = Blueprint('auth_snap', __name__, url_prefix='/snap')


def snap_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('snap_user'):
            session['snap_next'] = request.url
            flash("Inicia sesión para contribuir imágenes al dataset.", "snap")
            return redirect(url_for('auth_snap.login'))
        return f(*args, **kwargs)
    return decorated


@auth_snap_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('snap_user'):
        return redirect(url_for('siembra_snap.upload'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Completa todos los campos.", "snap_error")
            return render_template('snap_login.html', title="Iniciar Sesión | SiembraSnap")

        try:
            from pycognito import Cognito
            user_pool_id = os.getenv('COGNITO_USER_POOL_ID')
            client_id = os.getenv('COGNITO_CLIENT_ID')

            u = Cognito(user_pool_id, client_id, username=email)
            u.authenticate(password=password)

            # Decode JWT to extract group membership
            payload_b64 = u.id_token.split('.')[1]
            payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
            id_data = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
            grupos = id_data.get('cognito:groups', [])

            session['snap_user'] = email
            session['snap_is_admin'] = 'Admins' in grupos

            next_url = session.pop('snap_next', None)
            return redirect(next_url or url_for('siembra_snap.upload'))

        except Exception as e:
            print(f"[SiembraSnap] Login error: {e}")
            flash("Credenciales incorrectas o cuenta no confirmada.", "snap_error")

    return render_template('snap_login.html', title="Iniciar Sesión | SiembraSnap")


@auth_snap_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Completa todos los campos.", "snap_error")
            return render_template('snap_signup.html', title="Registro | SiembraSnap")

        try:
            from pycognito import Cognito
            user_pool_id = os.getenv('COGNITO_USER_POOL_ID')
            client_id = os.getenv('COGNITO_CLIENT_ID')

            u = Cognito(user_pool_id, client_id)
            u.register(email, password)
            flash("¡Registro exitoso! Revisa tu correo para el código de confirmación.", "snap_ok")
            return redirect(url_for('auth_snap.confirm'))

        except Exception as e:
            print(f"[SiembraSnap] Signup error: {e}")
            flash(f"Error: {str(e)}", "snap_error")

    return render_template('snap_signup.html', title="Registro | SiembraSnap")


@auth_snap_bp.route('/confirm', methods=['GET', 'POST'])
def confirm():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()

        if not email or not code:
            flash("Completa todos los campos.", "snap_error")
            return render_template('snap_confirm.html', title="Verificar Cuenta | SiembraSnap")

        try:
            from pycognito import Cognito
            user_pool_id = os.getenv('COGNITO_USER_POOL_ID')
            client_id = os.getenv('COGNITO_CLIENT_ID')

            u = Cognito(user_pool_id, client_id, username=email)
            u.confirm_sign_up(code)
            flash("¡Cuenta activada! Ya puedes iniciar sesión.", "snap_ok")
            return redirect(url_for('auth_snap.login'))

        except Exception as e:
            print(f"[SiembraSnap] Confirm error: {e}")
            flash(f"Error de verificación: {str(e)}", "snap_error")

    return render_template('snap_confirm.html', title="Verificar Cuenta | SiembraSnap")


@auth_snap_bp.route('/logout')
def logout():
    session.pop('snap_user', None)
    session.pop('snap_is_admin', None)
    session.pop('snap_next', None)
    flash("Sesión cerrada correctamente.", "snap_ok")
    return redirect(url_for('siembra_vision.index'))
