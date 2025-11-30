from flask import Blueprint, render_template, jsonify, request, send_file
import json
import pandas as pd
import io

# Importamos la lógica que acabamos de crear
from logic.monitor_logic import monitor_service

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

@siembra_link_bp.route('/api/iniciar_monitoreo', methods=['POST'])
def iniciar_monitoreo():
    data = request.json
    cultivo = data.get('cultivo')
    etapa = data.get('etapa')
    
    # Configuramos el monitor con lo que eligió el usuario
    monitor_service.set_configuracion_cultivo(etapa, cultivo)
    
    # Conectamos Arduino
    exito = monitor_service.conectar()
    
    if exito:
        return jsonify({"status": "ok", "msg": f"Monitoreando {cultivo} en etapa {etapa}"})
    else:
        return jsonify({"status": "error", "msg": "No se pudo conectar al Arduino (COM11)"}), 500

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
        "historial": monitor_service.datos_historial
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