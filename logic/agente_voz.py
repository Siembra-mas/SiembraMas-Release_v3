import os
import sys
import queue
import json
import subprocess
import threading
import re
import platform
import requests
import unicodedata
import pandas as pd
import sounddevice as sd
import vosk
from gtts import gTTS
from datetime import date, timedelta, datetime

# --- CONFIGURACIÓN DE RUTAS ---
# Ajustamos sys.path para poder importar 'logic.prediccion' y 'logic.catalogos'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Importamos las herramientas matemáticas existentes
from logic.prediccion import prediccion
from logic.catalogos import coordenadas, coordenadas_municipios

# Configuración del Modelo de Voz
RUTA_MODELO_VOSK = os.path.join(project_root, "model")
ARCHIVO_PARAMETROS = os.path.join(project_root, "parametros.json")

# ==================== SECCIÓN 1: UTILIDADES AGRÍCOLAS ====================

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8").upper()

def buscar_coords(ruta, lugar):
    pool = coordenadas_municipios if ruta == "Municipios" else coordenadas
    pool_norm = {normalizar_texto(k): v for k, v in pool.items()}
    return pool_norm.get(normalizar_texto(lugar), (None, None))

def obtener_clima_api(lat, lon):
    """Consulta API externa para datos recientes"""
    if not lat or not lon: return 0, 0
    try:
        fecha_fin = date.today()
        fecha_inicio = fecha_fin - timedelta(days=30)
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=precipitation_sum,relative_humidity_2m_mean&timezone=auto"
               f"&start_date={fecha_inicio}&end_date={fecha_fin}")
        resp = requests.get(url, timeout=5).json().get("daily", {})
        lluvia = sum(resp.get("precipitation_sum", [])) if resp.get("precipitation_sum") else 0
        hum = sum(resp.get("relative_humidity_2m_mean", [])) / len(resp.get("relative_humidity_2m_mean", [])) if resp.get("relative_humidity_2m_mean") else 0
        return lluvia, hum
    except:
        return 0, 0

def calcular_viabilidad_rapida(preds, optimos):
    """Algoritmo simplificado para respuesta de voz"""
    score = 0
    # Temp (40 pts), Lluvia (30 pts), Humedad (30 pts)
    if optimos["tmin"] <= preds["tmin"] <= optimos["tmax"]: score += 40
    elif abs(preds["tmin"] - optimos["tmin"]) < 5: score += 20
    
    if preds["precip"] >= optimos["p_opt"] * 0.8: score += 30
    elif preds["precip"] >= optimos["p_opt"] * 0.5: score += 15
    
    if abs(preds["hum"] - optimos["h_opt"]) < 20: score += 30
    return score

# ==================== SECCIÓN 2: PROCESAMIENTO INTELIGENTE ====================

def generar_respuesta_inteligente(params):
    """Combina datos de CSV + Predicciones + API para generar el texto"""
    ruta = params.get("ruta")
    lugar = params.get("lugar")
    intencion = params.get("intencion", "clima")

    lat, lon = buscar_coords(ruta, lugar)
    if not lat: return f"No tengo ubicación para {lugar}."

    # 1. Predicciones Matemáticas (Random Forest)
    try:
        df_pred = prediccion(ruta, lugar, mes_solicitado=datetime.now().month)
        if df_pred.empty: return f"Sin datos históricos para {lugar}."
        t_min, t_max = int(df_pred["Pred_TempMin"].iloc[0]), int(df_pred["Pred_tempMax"].iloc[0])
    except:
        return "Error calculando predicciones."

    # 2. Clima Reciente (API)
    lluvia, humedad = obtener_clima_api(lat, lon)

    if intencion == "clima":
        return (f"En {lugar} se prevén temperaturas de {t_min} a {t_max} grados. "
                f"Humedad reciente del {int(humedad)} por ciento.")

    elif intencion == "recomendacion":
        csv_path = os.path.join(project_root, "data", "condiciones_ideales", "CondicionesIdeales.csv")
        if not os.path.exists(csv_path): return "Error: Falta base de datos de cultivos."
        
        try:
            df = pd.read_csv(csv_path)
            mejores = []
            datos_actuales = {"tmin": t_min, "tmax": t_max, "precip": lluvia, "hum": humedad}

            for _, row in df.iterrows():
                try:
                    # Limpieza rápida de datos CSV
                    optimos = {
                        "tmin": float(str(row["Temp_min_optima"]).replace(',', '.')),
                        "tmax": float(str(row["Temp_max_optima"]).replace(',', '.')),
                        "p_opt": float(str(row["Lluvias_optima"]).replace(',', '.')),
                        "h_opt": float(str(row["Humedad"]).replace(',', '.'))
                    }
                    if calcular_viabilidad_rapida(datos_actuales, optimos) >= 70:
                        mejores.append(row["Cultivo"])
                except: continue

            if not mejores: return f"Las condiciones en {lugar} son difíciles por ahora."
            return f"Para {lugar} recomiendo: {', '.join(mejores[:4])}."
        except Exception as e:
            return f"Error analizando cultivos: {e}"

    return "No entendí la consulta."

# ==================== SECCIÓN 3: VOZ Y GEMMA (IO) ====================

def hablar(texto):
    print(f"🗣️ Bot: {texto}")
    try:
        tts = gTTS(text=texto, lang='es')
        # Guardamos el archivo
        archivo_audio = os.path.join(project_root, "respuesta.mp3")
        tts.save(archivo_audio)
        
        # --- CORRECCIÓN AQUÍ ---
        if platform.system() == "Windows":
            # Usamos os.startfile en lugar de os.system("start ...")
            # Esto soluciona el error de los espacios en la ruta.
            os.startfile(archivo_audio)
        else:
            # Para Linux/Mac seguimos usando mpg123
            # Añadimos comillas simples por si acaso hay espacios en Linux
            os.system(f'mpg123 "{archivo_audio}"')
            
    except Exception as e: 
        print(f"Error audio: {e}")

def interpretar_con_gemma(texto_voz):
    print(f"🧠 Gemma analizando: {texto_voz}")
    prompt = f"""
    Responde SOLO JSON. Intención agrícola.
    Usuario: "{texto_voz}"
    Formato: {{"intencion": "clima"|"recomendacion", "ruta": "Estados"|"Municipios", "lugar": "Nombre"}}
    Ej: "Lluvia en Xalapa" -> {{"intencion": "clima", "ruta": "Municipios", "lugar": "Xalapa"}}
    """
    try:
        proc = subprocess.run(["ollama", "run", "gemma:2b"], input=prompt, text=True, capture_output=True, encoding='utf-8', check=True)
        match = re.search(r"\{.*\}", proc.stdout.strip(), re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except: return None

# ==================== SECCIÓN 4: CONTROLADOR PRINCIPAL ====================

def ejecutar_agente():
    """Función maestra llamada por el Router"""
    # 1. Verificar modelo
    if not os.path.exists(RUTA_MODELO_VOSK):
        hablar("Error. No encuentro el modelo de voz.")
        return

    hablar("Te escucho.")
    
    # 2. Configurar micrófono
    q = queue.Queue()
    def callback(indata, frames, time, status): q.put(bytes(indata))

    try:
        voz_detectada = ""
        modelo = vosk.Model(RUTA_MODELO_VOSK)
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1, callback=callback):
            print("🎤 Escuchando...")
            rec = vosk.KaldiRecognizer(modelo, 16000)
            
            # Escuchar por máximo 6 segundos o hasta detectar frase
            inicio = datetime.now()
            while (datetime.now() - inicio).seconds < 6:
                data = q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    if res.get("text"):
                        voz_detectada = res["text"]
                        break
        
        # 3. Procesar
        if voz_detectada:
            print(f"📝 Recibido: {voz_detectada}")
            params = interpretar_con_gemma(voz_detectada)
            if params:
                respuesta = generar_respuesta_inteligente(params)
                hablar(respuesta)
            else:
                hablar("No entendí la instrucción.")
        else:
            hablar("No detecté voz.")

    except Exception as e:
        print(f"Error crítico agente: {e}")
        hablar("Ocurrió un error interno.")