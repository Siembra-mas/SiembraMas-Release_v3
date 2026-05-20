import sys
import os
from datetime import date, timedelta, datetime
from functools import lru_cache
from typing import Tuple, Optional
import unicodedata
import re
import requests
import pandas as pd
from flask import Blueprint, render_template, request, url_for, jsonify

# --- CONFIGURACIÓN DE RUTAS ---
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
project_root = os.path.dirname(current_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

# ======================== Dependencias del proyecto ==========================
from logic.prediccion import prediccion
from logic.cultivos import obtener_cultivos
from logic.catalogos import estados, municipios, coordenadas, coordenadas_municipios

general_bp = Blueprint('general', __name__)

# ================================= Utilidades ================================

def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return texto
    if isinstance(texto, str) and ',' in texto:
        texto = texto.replace(',', '.')
    texto = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode("utf-8")
    return texto.upper()

def slug_cultivo(nombre: str) -> str:
    s = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def buscar_coords(ruta: str, lugar: str) -> Tuple[Optional[float], Optional[float]]:
    if not lugar: return None, None
    pool = coordenadas_municipios if ruta == "Municipios" else coordenadas
    pool_norm = {normalizar_texto(k): v for k, v in pool.items()}
    return pool_norm.get(normalizar_texto(lugar), (None, None))

def obtener_clima_ultimos_30_dias(lat: float, lon: float):
    if not lat or not lon:
        return None, None

    fecha_fin = date.today()
    fecha_inicio = fecha_fin - timedelta(days=30)
    
    start_date = fecha_inicio.strftime("%Y-%m-%d")
    end_date = fecha_fin.strftime("%Y-%m-%d")

    api_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,relative_humidity_2m_mean&timezone=auto"
        f"&start_date={start_date}&end_date={end_date}"
    )

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        data = response.json().get("daily", {})
        
        lluvia_lista = data.get("precipitation_sum")
        humedad_lista = data.get("relative_humidity_2m_mean")

        if not lluvia_lista or not humedad_lista:
            return None, None

        precipitacion_total = sum(lluvia_lista)
        humedad_promedio = sum(humedad_lista) / len(humedad_lista) if len(humedad_lista) > 0 else 0

        return round(precipitacion_total, 1), round(humedad_promedio, 1)

    except requests.exceptions.RequestException:
        return None, None

def calcular_probabilidad_avanzada(preds: dict, optimos: dict, pesos=None, config=None):
    if pesos is None:
        pesos = {"tmin": 0.18, "tmax": 0.18, "tmed": 0.24, "precip": 0.24, "hum": 0.16}
    if config is None:
        config = {
            "precip_deficit_tol": 0.20,
            "hum_tolerancia": 0.10,
            "hum_rolloff": 0.50,
            "temp_holgura_c": 5.0,
            "tmed_holgura_c": 3.0,
        }

    def clamp01(x): return max(0.0, min(1.0, x))

    def score_precipitacion(pred, p_opt, deficit_tol):
        if p_opt <= 0: return 0.0
        if pred >= p_opt: return 1.0
        piso = p_opt * (1.0 - deficit_tol)
        if pred <= piso: return 0.0
        return (pred - piso) / (p_opt - piso)

    def score_humedad(pred, h_opt, tol_centro, rolloff):
        if h_opt <= 0: return 0.0
        delta_rel = abs(pred - h_opt) / h_opt
        if delta_rel <= tol_centro: return 1.0
        exceso = delta_rel - tol_centro
        if exceso >= rolloff: return 0.0
        return 1.0 - (exceso / rolloff)

    def score_temperatura(valor, rango_min, rango_max, holgura):
        if rango_min is None or rango_max is None: return 0.0
        if rango_min > rango_max: rango_min, rango_max = rango_max, rango_min
        if rango_min <= valor <= rango_max: return 1.0
        distancia = (rango_min - valor) if valor < rango_min else (valor - rango_max)
        if distancia >= holgura: return 0.0
        return 1.0 - (distancia / holgura)

    def score_temperatura_central(valor, t_opt, holgura):
        if t_opt is None or holgura is None or holgura <= 0: return 0.0
        d = abs(valor - t_opt)
        if d >= holgura: return 0.0
        return 1.0 - (d / holgura)

    p_opt = optimos.get("p_opt", (optimos["pmin"] + optimos["pmax"]) / 2.0)
    h_opt = optimos.get("h_opt", (optimos["hmin"] + optimos["hmax"]) / 2.0)

    tmin_pred = preds.get("tmin")
    tmax_pred = preds.get("tmax")
    tmed_pred = preds.get("tmed", None)
    if tmed_pred is None and (tmin_pred is not None and tmax_pred is not None):
        tmed_pred = (tmin_pred + tmax_pred) / 2.0

    tmed_opt = optimos.get("tmed_opt", None)
    if tmed_opt is None and ("tmin" in optimos and "tmax" in optimos):
        tmed_opt = (optimos["tmin"] + optimos["tmax"]) / 2.0

    s_tmin = score_temperatura(tmin_pred, optimos["tmin"], optimos["tmax"], config["temp_holgura_c"])
    s_tmax = score_temperatura(tmax_pred, optimos["tmin"], optimos["tmax"], config["temp_holgura_c"])
    s_tmed = score_temperatura_central(tmed_pred, tmed_opt, config["tmed_holgura_c"]) if tmed_pred is not None else 0.0
    s_prec = score_precipitacion(preds["precip"], p_opt, config["precip_deficit_tol"])
    s_hum  = score_humedad(preds["hum"], h_opt, config["hum_tolerancia"], config["hum_rolloff"])

    total_pesos = sum(pesos.values()) or 1.0
    score = (
        pesos.get("tmin", 0.0)   * s_tmin +
        pesos.get("tmax", 0.0)   * s_tmax +
        pesos.get("tmed", 0.0)   * s_tmed +
        pesos.get("precip", 0.0) * s_prec +
        pesos.get("hum", 0.0)    * s_hum
    ) / total_pesos

    valor = int(round(100 * clamp01(score)))
    return 99 if valor == 100 else valor

# ================================= Datos ====================================
MESES = ("Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre")
ANIOS = (datetime.now().year,)
def mes_actual_nombre() -> str: return MESES[datetime.now().month - 1]

try:
    csv_path = os.path.join(project_root, "data", "condiciones_ideales", "CondicionesIdeales.csv")
    CONDICIONES_DF = pd.read_csv(csv_path, encoding="utf-8")
    CONDICIONES_DF.columns = [col.strip().replace(' ', '_') for col in CONDICIONES_DF.columns]
    CONDICIONES_DF["Cultivo_normalizado"] = CONDICIONES_DF["Cultivo"].apply(normalizar_texto)
except Exception as e:
    print(f"Advertencia: No se cargó CondicionesIdeales.csv en {csv_path}: {e}")
    CONDICIONES_DF = pd.DataFrame()

@lru_cache(maxsize=128)
def _pred_cache(ruta: str, lugar: str, mes_solicitado: int):
    return prediccion(ruta=ruta, lugar=lugar, mes_solicitado=mes_solicitado)

# ================================== Rutas ====================================

@general_bp.route('/')
def landing():
    return render_template('landing.html', title="Inicio")

@general_bp.route('/siembra-mas')
def siembra_mas():
    context = {
        "title": "Siembra Más",
        "mes_sel": mes_actual_nombre(),
        "anio_sel": ANIOS[0],
        "recomendaciones": [],
        "estados": estados,
        "municipios": municipios,
        "meses": MESES,
        "anios": ANIOS,
        "coordenadas": coordenadas,
        "coordenadas_municipios": coordenadas_municipios,
        "temp_max": None, "temp_min": None, "temp_media": None,
        "precipitacion": None, "humedad": None, "nombre_mes": None,
        "estado_sel": None, "municipio_sel": None
    }
    return render_template('index.html', **context)

# --- NUEVA RUTA API PARA FETCH ---
@general_bp.route('/api/municipios')
def api_municipios():
    """Devuelve la lista de municipios en formato JSON para consumo vía Fetch"""
    return jsonify(municipios)

@general_bp.route('/generar_analisis', methods=['POST'])
def generar_analisis():
    estado_input = request.form.get("estado")
    municipio_input = request.form.get("municipio")
    
    # --- LOGICA CORREGIDA PARA 'GENERAL' ---
    # Si el municipio es "General", "Seleccionar..." o está vacío, analizamos el Estado completo.
    if municipio_input and municipio_input not in ["Seleccionar...", "General", ""]:
        lugar = municipio_input
        ruta = "Municipios"
    else:
        lugar = estado_input
        ruta = "Estados"
    # ---------------------------------------

    mes_texto = mes_actual_nombre()
    anio = ANIOS[0]
    mes_solicitado = MESES.index(mes_texto) + 1

    temp_min = temp_max = precipitacion = humedad = None
    lat, lon = None, None

    # 1. Obtener Clima y Coordenadas
    if lugar:
        try:
            df_pred = _pred_cache(ruta, lugar, mes_solicitado)
            if not df_pred.empty:
                temp_min, temp_max = int(df_pred["Pred_TempMin"].iloc[0]), int(df_pred["Pred_tempMax"].iloc[0])
                lat, lon = buscar_coords(ruta, lugar)
                
                precipitacion, humedad = obtener_clima_ultimos_30_dias(lat, lon)
                
        except Exception as e:
            print(f"Error obteniendo predicciones: {e}")

    recomendaciones = []
    
    # 2. Generar Recomendaciones
    if lugar and all(v is not None for v in [temp_min, temp_max, precipitacion, humedad]):
        try:
            if ruta == "Estados":
                ruta_csv_cultivos = os.path.join(project_root, "data", "Ideal", "CultivoEstado.csv")
            else:
                ruta_csv_cultivos = os.path.join(project_root, "data", "Ideal", "CultivoMunicipio.csv")
            
            lista_cultivos_zona = obtener_cultivos(ruta_csv_cultivos).get(lugar, [])
            lista_cultivos_zona_norm = [normalizar_texto(c) for c in lista_cultivos_zona]

            cultivos_unicos = CONDICIONES_DF["Cultivo"].unique()
            preds = {"tmin": temp_min, "tmax": temp_max, "precip": precipitacion, "hum": humedad}

            for cultivo in cultivos_unicos:
                cond = CONDICIONES_DF[CONDICIONES_DF["Cultivo"] == cultivo]
                if not cond.empty:
                    lluvia_opt  = float(str(cond["Lluvias_optima"].iloc[0]).replace(',', '.'))
                    humedad_opt = float(str(cond["Humedad"].iloc[0]).replace(',', '.'))
                    optimos = {
                        "tmin": float(str(cond["Temp_min_optima"].iloc[0]).replace(',', '.')),
                        "tmax": float(str(cond["Temp_max_optima"].iloc[0]).replace(',', '.')),
                        "pmin": lluvia_opt * 0.8,  "pmax": lluvia_opt * 1.2,
                        "hmin": humedad_opt * 0.9, "hmax": humedad_opt * 1.1,
                        "p_opt": lluvia_opt, "h_opt": humedad_opt,
                    }
                    
                    prob = calcular_probabilidad_avanzada(preds, optimos)

                    if prob >= 70: 
                            texto = "Alta probabilidad de éxito."
                            clase_viabilidad = "bg-green"   
                    elif prob >= 40: 
                            texto = "La siembra es posible con precauciones."
                            clase_viabilidad = "bg-yellow"  
                    else: 
                            texto = "No se recomienda la siembra."
                            clase_viabilidad = "bg-red"

                    es_de_zona = normalizar_texto(cultivo) in lista_cultivos_zona_norm

                    recomendaciones.append({
                        "cultivo": cultivo,
                        "prob": prob,
                        "texto": texto,
                        "clase_viabilidad": clase_viabilidad,
                        "img_slug": slug_cultivo(cultivo),
                        "es_zona": es_de_zona
                    })

        except Exception as e:
            print(f"Error generando recomendaciones: {e}")

    recomendaciones = sorted(recomendaciones, key=lambda x: x['prob'], reverse=True)

    context = {
        "title": "Análisis Generado",
        "ruta_sel": ruta, 
        "estado_sel": estado_input, 
        "municipio_sel": municipio_input,
        "mes_sel": mes_texto, 
        "anio_sel": anio, 
        "recomendaciones": recomendaciones,
        "temp_max": temp_max, 
        "temp_min": temp_min, 
        "temp_media": int((temp_min + temp_max) / 2) if temp_min is not None else None,
        "precipitacion": precipitacion, 
        "humedad": humedad, 
        "nombre_mes": mes_texto if lugar else None,
        "latitud_mapa": lat if lat else 19.1738,
        "longitud_mapa": lon if lon else -96.1342,
        "estados": estados, 
        "municipios": municipios,
        "meses": MESES, 
        "anios": ANIOS
    }
    
    return render_template('index.html', **context)

@general_bp.route('/precios')
def precios():
    return render_template('precios.html', title="Planes y Precios")

@general_bp.route('/privacidad')
def privacidad():
    return render_template('privacy.html', title="Aviso de Privacidad")

@general_bp.route('/terminos')
def terminos():
    return render_template('privacy.html', title="Términos de Uso")