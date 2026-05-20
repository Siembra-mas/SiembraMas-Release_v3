from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import boto3
import os
from datetime import datetime
from PIL import Image
from routes.auth_snap import snap_login_required

siembra_snap_bp = Blueprint('siembra_snap', __name__, url_prefix='/snap')

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UPLOADS_DIR = os.path.join(_BASE_DIR, 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
CULTIVOS = ['tomate', 'maiz', 'papa', 'frijol', 'chile', 'cebolla', 'general']
ESTADOS = ['sano', 'enfermo', 'plaga', 'deficiencia']


def _get_s3():
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _username_from_email(email):
    return email.split('@')[0] if email and '@' in email else 'usuario'


@siembra_snap_bp.route('/upload', methods=['GET', 'POST'])
@snap_login_required
def upload():
    if request.method == 'GET':
        return render_template(
            'snap_upload.html',
            title="Contribuir Imágenes | SiembraSnap",
            cultivos=CULTIVOS,
            estados=ESTADOS,
            snap_user=session.get('snap_user'),
            snap_is_admin=session.get('snap_is_admin', False),
        )

    files = request.files.getlist('file')
    cultivo = request.form.get('cultivo', 'general').strip().lower().replace(' ', '_')
    estado = request.form.get('estado', 'sano').strip().lower().replace(' ', '_')
    usuario = _username_from_email(session.get('snap_user', ''))

    if not files or files[0].filename == '':
        flash("No seleccionaste ningún archivo.", "snap_error")
        return redirect(url_for('siembra_snap.upload'))

    os.makedirs(_UPLOADS_DIR, exist_ok=True)
    s3 = _get_s3()
    bucket = os.getenv('AWS_S3_BUCKET', 'siembrasnap-prod-2026')

    exitos = 0
    for i, file in enumerate(files):
        if not (file and _allowed(file.filename)):
            continue
        timestamp = datetime.now().strftime('%d-%m-%y_%H-%M-%S')
        nombre = f"{cultivo}-{estado}-{timestamp}_{i}.jpg"
        ruta_temp = os.path.join(_UPLOADS_DIR, nombre)
        try:
            img = Image.open(file).convert('RGB')
            img.save(ruta_temp, 'JPEG', optimize=True, quality=85)
            s3.upload_file(ruta_temp, bucket, f"{usuario}/{nombre}")
            os.remove(ruta_temp)
            exitos += 1
        except Exception as e:
            print(f"[SiembraSnap] Upload error: {e}")

    if exitos:
        flash(f"¡{exitos} imagen(es) subida(s) con éxito! Gracias por contribuir al dataset.", "snap_ok")
        return redirect(url_for('siembra_snap.gallery'))
    else:
        flash("No se pudo subir ninguna imagen. Verifica el formato (JPG, PNG, WEBP).", "snap_error")
        return redirect(url_for('siembra_snap.upload'))


@siembra_snap_bp.route('/gallery')
@snap_login_required
def gallery():
    user_email = session.get('snap_user', '')
    usuario_id = _username_from_email(user_email)
    es_admin = session.get('snap_is_admin', False)
    prefijo = '' if es_admin else f'{usuario_id}/'

    s3 = _get_s3()
    bucket = os.getenv('AWS_S3_BUCKET', 'siembrasnap-prod-2026')

    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefijo)
        imagenes = []
        for obj in response.get('Contents', []):
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': obj['Key']},
                ExpiresIn=3600,
            )
            imagenes.append({'url': url, 'key': obj['Key'], 'fecha': obj['LastModified']})
        imagenes.sort(key=lambda x: x['fecha'], reverse=True)

        # Group by user folder for admin accordion
        agrupadas = {}
        if es_admin:
            for img in imagenes:
                partes = img['key'].split('/')
                carpeta = partes[0] if len(partes) > 1 else 'general'
                agrupadas.setdefault(carpeta, []).append(img)

        return render_template(
            'snap_gallery.html',
            title="Mi Galería | SiembraSnap",
            imagenes=imagenes,
            imagenes_agrupadas=agrupadas,
            admin=es_admin,
            snap_user=user_email,
            total=len(imagenes),
        )

    except Exception as e:
        print(f"[SiembraSnap] Gallery error: {e}")
        flash("Error al cargar la galería. Verifica la conexión con AWS.", "snap_error")
        return redirect(url_for('siembra_snap.upload'))
