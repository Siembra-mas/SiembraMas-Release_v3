# Ubicación: logic/vision_logic.py
import os
import sys
import numpy as np
from PIL import Image

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import (
        InputLayer, Dense, GlobalAveragePooling2D,
        RandomFlip, RandomRotation, Rescaling
    )
    from tensorflow.keras.applications import MobileNetV2
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow no disponible — SiembraVision en modo sin IA.")

# --- 1. CONFIGURACIÓN DE RUTAS E IMPORTACIONES ---

base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.dirname(base_dir) 

if project_root not in sys.path:
    sys.path.append(project_root)

# Importación robusta de la lista de clases y la función de descripción
try:
    # Intento 1: Si ejecutamos como módulo
    from logic.enfermedad import clase, obtener_descripcion
except ImportError:
    try:
        # Intento 2: Importación directa
        from enfermedad import clase, obtener_descripcion
    except ImportError:
        print("⚠️ ADVERTENCIA: No se pudo importar 'enfermedad.py'. Usando valores por defecto.")
        clase = []
        def obtener_descripcion(x): return "Descripción no disponible."

# Configuración del modelo
RUTA_PESOS = os.path.join(project_root, 'model', 'siembra_plus_doctor.h5')
IMG_SIZE = 224
CLASS_NAMES = clase 
NUM_CLASSES = len(CLASS_NAMES)

# Variable global (Singleton)
_model_instance = None

# --- 2. DEFINICIÓN DEL MODELO ---
def construir_model():
    """Reconstruye la arquitectura del modelo MobileNetV2."""
    if not TF_AVAILABLE:
        return None
    IMG_SHAPE = (IMG_SIZE, IMG_SIZE, 3)
    base_model = MobileNetV2(
        input_shape=IMG_SHAPE, include_top=False, weights=None
    )
    base_model.trainable = False
    
    data_augmentation = Sequential([
        RandomFlip("horizontal_and_vertical"),
        RandomRotation(0.2),
    ], name="data_augmentation")
    
    rescaling = Rescaling(1./127.5, offset=-1, name="rescaling")
    
    model = Sequential([
        InputLayer(input_shape=IMG_SHAPE, name="input_layer"), 
        data_augmentation,
        rescaling,
        base_model,
        GlobalAveragePooling2D(name="global_avg_pool"),
        Dense(128, activation='relu', name="dense_1"),
        Dense(NUM_CLASSES, activation='softmax', name="output_layer")
    ])
    
    # Inicializar con entrada dummy
    model(tf.zeros([1, IMG_SIZE, IMG_SIZE, 3]))
    return model

def obtener_model():
    """Patrón Singleton para cargar el modelo solo una vez."""
    global _model_instance
    if _model_instance is None:
        print("⏳ Cargando modelo de IA por primera vez...")
        try:
            model = construir_model()
            
            if os.path.exists(RUTA_PESOS):
                model.load_weights(RUTA_PESOS)
                print(f"✅ Pesos cargados desde: {RUTA_PESOS}")
                _model_instance = model
            else:
                print(f"❌ ERROR CRÍTICO: No se encontró el archivo de pesos en: {RUTA_PESOS}")
                _model_instance = None
        except Exception as e:
            print(f"❌ Error construyendo/cargando modelo: {e}")
            _model_instance = None
            
    return _model_instance

# --- 3. LÓGICA DE PREDICCIÓN ---
def procesar_prediccion(img_pil):
    """
    Recibe una imagen PIL, la procesa y devuelve un diccionario JSON-safe con diagnóstico y descripción.
    """
    if not TF_AVAILABLE:
        return {
            "error": "El análisis de imágenes no está disponible en esta instancia.",
            "diagnostico": "Servicio no disponible",
            "descripcion": "SiembraVision requiere TensorFlow. Contacta al administrador.",
            "id": -1,
            "status": "unavailable"
        }
    try:
        model = obtener_model()
        
        if model is None:
            return {
                "error": "El modelo de IA no está disponible (no se cargaron los pesos).",
                "diagnostico": "Error de Sistema",
                "descripcion": "No se pudo cargar el cerebro de la IA.",
                "id": -1
            }

        # Pre-procesamiento
        img_resized = img_pil.resize((IMG_SIZE, IMG_SIZE))
        img_array = np.array(img_resized)
        
        if img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]
            
        img_array = tf.expand_dims(img_array, 0) 

        # Predicción
        predictions = model.predict(img_array, verbose=0)
        score = tf.nn.softmax(predictions[0])
        
        class_id_raw = np.argmax(score)
        class_id = int(class_id_raw)
        
        # Obtener nombre y descripción
        if 0 <= class_id < len(CLASS_NAMES):
            class_name = CLASS_NAMES[class_id]
            descripcion_texto = obtener_descripcion(class_name) # <--- Aquí obtenemos la descripción
        else:
            class_name = f"Desconocido (ID: {class_id})"
            descripcion_texto = "No se ha podido identificar el problema con certeza."
        
        return {
            "diagnostico": class_name,
            "descripcion": descripcion_texto, # <--- Enviamos la descripción al frontend
            "id": class_id,
            "status": "success"
        }

    except Exception as e:
        print(f"❌ Error durante la predicción: {e}")
        return {
            "diagnostico": "Error al analizar",
            "descripcion": "Ocurrió un error técnico al procesar la imagen.",
            "id": -1,
            "error": str(e),
            "status": "error"
        }