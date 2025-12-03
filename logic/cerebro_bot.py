import os
import pandas as pd
import requests
import datetime
import asyncio
import edge_tts
import unicodedata
import uuid
from groq import Groq
from gtts import gTTS


# --- IMPORTACIÓN DE CATÁLOGOS ---
try:
    from logic.catalogos import coordenadas
except ImportError:
    coordenadas = {}
    print("Advertencia: No se encontró logic/catalogos.py")

# --- CONFIGURACIÓN ---
os.environ["GROQ_API_KEY"] = ""

# --- CARGA DE DATOS (CSV) ---
# 1. Calculamos la ruta absoluta basada en la ubicación de este archivo
current_dir = os.path.dirname(os.path.abspath(__file__))  # Carpeta 'logic'
project_root = os.path.dirname(current_dir)             # Carpeta 'SiembraMas...'
csv_path = os.path.join(project_root, "data", "condiciones_ideales", "CondicionesIdeales.csv")

# 2. Intentamos cargar el CSV
try:
    if os.path.exists(csv_path):
        df_cultivos = pd.read_csv(csv_path)
        print(f"✅ Base de datos de cultivos cargada desde: {csv_path}")
    else:
        print(f"⚠️ Alerta: No encontré el CSV en {csv_path}")
        df_cultivos = pd.DataFrame() # DataFrame vacío para no romper el código
except Exception as e:
    print(f"❌ Error leyendo CSV: {e}")
    df_cultivos = pd.DataFrame()

# --- UTILIDADES DE TEXTO ---
def normalizar(texto):
    """Elimina acentos y pasa a minúsculas"""
    if not isinstance(texto, str): return ""
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.lower()

def buscar_coords_en_texto(mensaje):
    """Busca si el mensaje menciona algún lugar del catálogo"""
    mensaje_norm = normalizar(mensaje)
    for lugar, (lat, lon) in coordenadas.items():
        if normalizar(lugar) in mensaje_norm:
            return lugar, lat, lon
    return None, None, None

# --- API CLIMA ---
def obtener_clima_real(lat, lon):
    try:
        today = datetime.date.today()
        end_date = today + datetime.timedelta(days=7)
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone=auto&start_date={today}&end_date={end_date}"
        )
        response = requests.get(url)
        data = response.json()
        daily = data.get("daily", {})
        if not daily: return "Datos climáticos no disponibles."
        
        temp_prom = (sum(daily["temperature_2m_max"]) + sum(daily["temperature_2m_min"])) / (2 * len(daily["temperature_2m_max"]))
        return f"Temp Promedio: {round(temp_prom, 1)}°C, Lluvia Semanal: {round(sum(daily['precipitation_sum']), 1)}mm."
    except:
        return "No se pudo obtener el clima."

# --- CEREBRO (LLM) ---
try:
    client = Groq()
except:
    print("Advertencia: No se pudo conectar con Groq. Revisa tu API KEY.")
    client = None

def transcribir_audio_groq(filepath):
    if not client: return None
    try:
        with open(filepath, "rb") as file:
            return client.audio.transcriptions.create(
                file=(filepath, file.read()), model="whisper-large-v3",
                language="es", response_format="json"
            ).text
    except Exception as e:
        print(f"Error transcripción: {e}")
        return None

def consultar_cerebro(mensaje_usuario, historial, lat_usuario=None, lon_usuario=None):
    if not client: return "Error: Cerebro desconectado (API Key)."
    
    # 1. Detectar ubicación
    lugar_detectado, lat_cat, lon_cat = buscar_coords_en_texto(mensaje_usuario)
    
    lat_final = lat_cat if lugar_detectado else lat_usuario
    lon_final = lon_cat if lugar_detectado else lon_usuario
    nombre_ubicacion = lugar_detectado if lugar_detectado else "tu ubicación actual"

    # 2. Consultar Clima
    if lat_final and lon_final:
        datos_clima = obtener_clima_real(lat_final, lon_final)
        info_clima = f"Para {nombre_ubicacion}: {datos_clima}"
    else:
        info_clima = "No tengo ubicación (activa el GPS o menciona un estado)."

    # 3. Preparar datos
    datos_cultivos_str = df_cultivos.to_csv(index=False) if not df_cultivos.empty else "No hay base de datos de cultivos."

    # --- AQUÍ ESTÁ EL CAMBIO CLAVE ---
    prompt_sistema = f"""
    Eres 'SiembraBot', un asistente INTELIGENTE y EXCLUSIVO para agricultura.
    
    CONTEXTO:
    - Ubicación analizada: {nombre_ubicacion}
    - Clima actual: {info_clima}
    - Base de conocimientos: {datos_cultivos_str}
    
    REGLAS ESTRICTAS DE SEGURIDAD (GUARDRAILS):
    1. TU ÚNICO TEMA es: agricultura, siembra, cultivos, clima, plagas, enfermedades agrícolas y precios de mercado.
    2. SI EL USUARIO PREGUNTA OTRA COSA (Cocina, deportes, política, chistes generales, programación, etc.):
       - DEBES NEGARTE a responder.
       - Di una frase como: "Soy un experto agrícola, no puedo ayudarte con recetas/ese tema." o "Mi enfoque es 100% el campo, pregúntame sobre cultivos."
       - NO intentes cocinar ni dar instrucciones fuera del agro.
       
    INSTRUCCIONES DE RESPUESTA:
    - Cruza el clima con los cultivos para dar recomendaciones técnicas.
    - Sé breve (máximo 3 oraciones).
    - Usa un tono profesional de ingeniero agrónomo.
    """
    
    mensajes_api = [{"role": "system", "content": prompt_sistema}]
    if historial:
        mensajes_api.extend(historial[-4:]) 
    mensajes_api.append({"role": "user", "content": mensaje_usuario})

    try:
        chat = client.chat.completions.create(
            messages=mensajes_api,
            model="llama-3.3-70b-versatile", temperature=0.3 # Bajamos temperatura para que sea más obediente
        )
        return chat.choices[0].message.content
    except Exception as e:
        return f"Error en cerebro: {str(e)}"

# --- GENERACIÓN DE AUDIO ---
async def _generar_edge_tts(texto, archivo_salida):
    voz = "es-MX-JorgeNeural"
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(archivo_salida)

def generar_audio_respuesta(texto, static_folder):
    filename = f"resp_{uuid.uuid4().hex}.mp3"
    audio_dir = os.path.join(static_folder, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    filepath = os.path.join(audio_dir, filename)
    
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            asyncio.run(_generar_edge_tts(texto, filepath))
        else:
            loop.run_until_complete(_generar_edge_tts(texto, filepath))
            
        return f"audio/{filename}"
    except Exception as e:
        print(f"Fallo EdgeTTS: {e}. Usando Google TTS.")
        try:
            tts = gTTS(text=texto, lang='es', tld='com.mx')
            tts.save(filepath)
            return f"audio/{filename}"
        except:
            return None