from flask import Blueprint, render_template, jsonify, request, send_file
import json
import pandas as pd
import io
from datetime import datetime

from logic.monitor_logic import monitor_service, listar_puertos_seriales, detectar_arduino
from logic import db, geo_mexico
from logic.reverse_geocode import reverse_geocode

siembra_link_bp = Blueprint('siembra_link', __name__)

@siembra_link_bp.route('/siembra-link')
def index():
    # Usamos el servicio para obtener la lista de cultivos de la etapa 1 por defecto
    datos_etapa_1 = monitor_service.dict_fases.get("1")
    lista_cultivos = sorted(datos_etapa_1['Cultivo'].unique()) if datos_etapa_1 is not None else []
    
    return render_template('siembra_link.html', 
                           title="Siembra Link (IoT)", 
                           lista_cultivos=lista_cultivos)

# --- RUTAS API (Para que JavaScript hable con Python) ---

@siembra_link_bp.route('/api/escanear_puertos')
def escanear_puertos():
    """Devuelve los puertos seriales disponibles y el Arduino detectado automáticamente."""
    puertos = listar_puertos_seriales()
    arduino = detectar_arduino()
    return jsonify({
        "puertos": puertos,
        "arduino_detectado": arduino
    })

@siembra_link_bp.route('/api/iniciar_monitoreo', methods=['POST'])
def iniciar_monitoreo():
    data = request.json or {}
    cultivo = data.get('cultivo')
    etapa = data.get('etapa')
    puerto = data.get('puerto')  # Puerto opcional; si viene vacío, se auto-detecta
    estado = data.get('estado')
    municipio = data.get('municipio')
    lat = data.get('lat')
    lon = data.get('lon')
    intervalo = data.get('intervalo_guardado_segundos', 300)
    duracion = data.get('duracion_minutos', 5)

    if not cultivo:
        return jsonify({"status": "error", "msg": "Debes seleccionar un cultivo."}), 400

    if not estado:
        return jsonify({"status": "error", "msg": "Debes ingresar o detectar el Estado antes de iniciar el monitoreo."}), 400

    monitor_service.set_configuracion_cultivo(etapa, cultivo)
    monitor_service.set_ubicacion({
        "estado": estado,
        "municipio": municipio,
        "lat": lat,
        "lon": lon
    }, fuente="geolocation" if lat else "manual")

    exito = monitor_service.conectar(puerto=puerto or None, intervalo_guardado=intervalo, duracion_minutos=duracion)

    if exito:
        return jsonify({
            "status": "ok",
            "msg": f"Monitoreando {cultivo} ({estado}{', ' + municipio if municipio else ''})",
            "puerto": monitor_service.puerto_detectado,
            "sesion_id": monitor_service.sesion_id,
            "estado": estado,
            "municipio": municipio,
            "duracion_minutos": duracion,
            "intervalo_guardado_segundos": monitor_service.intervalo_guardado_segundos
        })
    else:
        puertos_disp = [p["puerto"] for p in listar_puertos_seriales()]
        msg = "No se encontró ningún dispositivo." if not puertos_disp else f"No se pudo conectar. Puertos disponibles: {', '.join(puertos_disp)}"
        return jsonify({"status": "error", "msg": msg}), 500

@siembra_link_bp.route('/api/detener_monitoreo', methods=['POST'])
def detener_monitoreo():
    monitor_service.desconectar()
    return jsonify({"status": "ok", "msg": "Monitoreo detenido"})

@siembra_link_bp.route('/api/obtener_datos')
def obtener_datos():
    """Devuelve la última lectura, estado y REFERENCIAS para la UI"""
    if not monitor_service.running:
        return jsonify({"activo": False})
    
    return jsonify({
        "activo": True,
        "actual": monitor_service.ultima_lectura,
        # NUEVO: Enviamos las referencias para pintar las cajas
        "referencias": monitor_service.referencias_visuales,
        "historial": monitor_service.datos_historial,
        "ubicacion": monitor_service.ubicacion_actual
    })

@siembra_link_bp.route('/api/descargar_csv')
def descargar_csv():
    """Genera un CSV con los datos capturados en memoria"""
    if not monitor_service.datos_historial:
        return "No hay datos para descargar", 404
        
    df = pd.DataFrame(monitor_service.datos_historial)
    
    # Crear buffer en memoria
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(output,
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name="datos_siembra_iot.csv")


# --- UBICACIÓN (geolocalización del navegador -> estado/municipio) ---

@siembra_link_bp.route('/api/siembra_link/ubicacion', methods=['POST'])
def resolver_ubicacion():
    """Recibe {lat, lon} del navegador, resuelve estado/municipio vía
    reverse geocoding y lo guarda como ubicación de la sesión de monitoreo."""
    data = request.json or {}
    lat = data.get('lat')
    lon = data.get('lon')

    if lat is None or lon is None:
        return jsonify({"status": "error", "msg": "Faltan coordenadas."}), 400

    resultado = reverse_geocode(lat, lon)
    monitor_service.set_ubicacion(resultado, fuente="geolocation")

    if resultado["encontrado"]:
        return jsonify({
            "status": "ok",
            "estado": resultado["estado"],
            "municipio": resultado["municipio"],
        })
    return jsonify({"status": "error", "msg": resultado["error"] or "No se pudo determinar la ubicación."}), 200


# --- CATÁLOGO GEOGRÁFICO NACIONAL (32 estados, ~2478 municipios) ---

@siembra_link_bp.route('/api/geo/estados')
def geo_estados():
    return jsonify(geo_mexico.listar_estados())


@siembra_link_bp.route('/api/geo/municipios/<estado>')
def geo_municipios(estado):
    return jsonify(geo_mexico.listar_municipios(estado))


# --- COBERTURA (estados/municipios con lecturas en Mongo o local) ---

@siembra_link_bp.route('/api/siembra_link/cobertura')
def cobertura_nacional():
    usar_local = request.args.get('local', 'false').lower() in ('1', 'true', 'yes')
    if db.is_configured() and not usar_local:
        cobertura_datos = db.cobertura() or []
    else:
        cobertura_datos = db.cobertura_local() or []

    mapa = {}
    for c in cobertura_datos:
        mapa.setdefault(c["estado"], {})[c["municipio"]] = {
            "conteo": c["conteo"], "ultima_fecha": c["ultima_fecha"]
        }

    estados_out = []
    for estado in geo_mexico.listar_estados():
        municipios_estado = geo_mexico.listar_municipios(estado)
        datos_estado = mapa.get(estado, {})
        municipios_out = [
            {
                "nombre": m,
                "tiene_datos": m in datos_estado,
                "conteo": datos_estado.get(m, {}).get("conteo", 0),
            }
            for m in municipios_estado
        ]
        estados_out.append({
            "nombre": estado,
            "tiene_datos": bool(datos_estado) or (None in datos_estado),
            "conteo": sum(v["conteo"] for v in datos_estado.values()),
            "municipios": municipios_out,
        })

    return jsonify({"status": "ok", "estados": estados_out, "modo": "local" if not db.is_configured() or usar_local else "cloud"})


# --- CRUD DE LECTURAS (PRODUCCIÓN MONGO + FALLBACK LOCAL PARA TESTING) ---

@siembra_link_bp.route('/api/siembra_link/lecturas', methods=['GET'])
def listar_lecturas_api():
    filtro = {}
    estado = request.args.get('estado')
    municipio = request.args.get('municipio')
    cultivo = request.args.get('cultivo')
    usar_local = request.args.get('local', 'false').lower() in ('1', 'true', 'yes')

    if estado:
        filtro['estado'] = estado
    if municipio:
        filtro['municipio'] = municipio
    if cultivo:
        filtro['cultivo'] = cultivo

    limit = request.args.get('limit', 200, type=int)
    skip = request.args.get('skip', 0, type=int)

    if db.is_configured() and not usar_local:
        lecturas = db.listar_lecturas(filtro, limit=limit, skip=skip)
        modo = "mongodb"
    else:
        lecturas = db.listar_lecturas_local(filtro, limit=limit, skip=skip)
        modo = "local_testing"

    return jsonify({"status": "ok", "lecturas": lecturas or [], "modo": modo})


@siembra_link_bp.route('/api/siembra_link/lecturas', methods=['POST'])
def crear_lectura_api():
    data = request.json or {}
    fecha = data.get("fecha")
    try:
        mes = datetime.strptime(fecha, "%Y-%m-%d").month if fecha else None
    except ValueError:
        mes = None

    doc = {
        "fecha": fecha,
        "mes": mes,
        "hora": data.get("hora"),
        "timestamp": data.get("hora"),
        "temperatura": data.get("temperatura"),
        "humedad_ambiente": data.get("humedad_ambiente"),
        "humedad_suelo_pct": data.get("humedad_suelo_pct"),
        "precipitacion_raw": data.get("precipitacion_raw"),
        "cultivo": data.get("cultivo"),
        "etapa": data.get("etapa"),
        "estado": data.get("estado"),
        "municipio": data.get("municipio"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "fuente_ubicacion": "manual",
        "sesion_id": None,
        "origen": "manual",
    }

    if not doc["estado"] or not doc["fecha"]:
        return jsonify({"status": "error", "msg": "Estado y fecha son obligatorios."}), 400

    if db.is_configured():
        exito = db.guardar_lectura(doc)
    else:
        exito = db.guardar_lectura_local(doc)

    return jsonify({"status": "ok" if exito else "error", "modo": "mongodb" if db.is_configured() else "local"}), (200 if exito else 500)


@siembra_link_bp.route('/api/siembra_link/lecturas/<id_lectura>', methods=['PUT'])
def actualizar_lectura_api(id_lectura):
    data = request.json or {}
    campos_editables = (
        "fecha", "hora", "temperatura", "humedad_ambiente", "humedad_suelo_pct",
        "precipitacion_raw", "cultivo", "etapa", "estado", "municipio", "lat", "lon",
    )
    cambios = {k: data[k] for k in campos_editables if k in data}
    if "fecha" in cambios:
        try:
            cambios["mes"] = datetime.strptime(cambios["fecha"], "%Y-%m-%d").month
        except ValueError:
            cambios["mes"] = None

    if db.is_configured():
        exito = db.actualizar_lectura(id_lectura, cambios)
    else:
        exito = db.actualizar_lectura_local(id_lectura, cambios)

    return jsonify({"status": "ok" if exito else "error"}), (200 if exito else 404)


@siembra_link_bp.route('/api/siembra_link/lecturas/<id_lectura>', methods=['DELETE'])
def eliminar_lectura_api(id_lectura):
    if db.is_configured():
        exito = db.eliminar_lectura(id_lectura)
    else:
        exito = db.eliminar_lectura_local(id_lectura)

    return jsonify({"status": "ok" if exito else "error"}), (200 if exito else 404)


# ============================================================================
# NUEVA RUTA Y FUNCIÓN LOCAL PARA ENTORNO DE TESTING
# ============================================================================

@siembra_link_bp.route('/api/siembra_link/local', methods=['GET', 'POST'])
def local_api():
    """
    Endpoint de testing local:
    - GET: Devuelve estado local, lecturas guardadas localmente y resumen de clima local.
    - POST: Ejecuta lectura desde hardware local (o datos de prueba) y guarda en local.
    """
    if request.method == 'GET':
        estado = request.args.get('estado', 'Local')
        municipio = request.args.get('municipio')
        mes = request.args.get('mes', type=int)
        
        lecturas_locales = db.listar_lecturas_local(limit=50)
        resumen = db.resumen_clima_local(estado=estado, municipio=municipio, mes=mes)
        
        return jsonify({
            "status": "ok",
            "modo": "testing_local",
            "total_lecturas_locales": len(lecturas_locales),
            "ultima_lectura": monitor_service.ultima_lectura,
            "resumen_clima_local": resumen,
            "lecturas": lecturas_locales
        })

    data = request.json or {}
    puerto = data.get('puerto')
    cultivo = data.get('cultivo', 'Tomate')
    etapa = data.get('etapa', '1')
    estado = data.get('estado', 'Local')
    municipio = data.get('municipio', 'Testing')
    simular = data.get('simular', False)
    datos_muestra = data.get('datos_muestra')

    resultado = monitor_service.local(
        puerto=puerto,
        etapa=etapa,
        cultivo=cultivo,
        estado=estado,
        municipio=municipio,
        simular=simular,
        datos_muestra=datos_muestra
    )
    return jsonify(resultado)


def local(*args, **kwargs):
    """Función de Siembra Link para testing local."""
    return monitor_service.local(*args, **kwargs)