import os
import sys
import numpy as np
from PIL import Image

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from logic.enfermedad import clase, obtener_descripcion
except ImportError:
    try:
        from enfermedad import clase, obtener_descripcion
    except ImportError:
        clase = []
        def obtener_descripcion(x): return "Descripción no disponible."

IMG_SIZE = 224
CLASS_NAMES = clase

# ── Rutas de modelos ──────────────────────────────────────────────────────────
RUTA_ONNX = os.path.join(project_root, 'model', 'siembra_plus_doctor.onnx')
RUTA_H5   = os.path.join(project_root, 'model', 'siembra_plus_doctor.h5')

# ── Intentar cargar backend disponible ───────────────────────────────────────
_onnx_session = None
_tf_model     = None

def _init_onnx():
    global _onnx_session
    if not os.path.exists(RUTA_ONNX):
        return False
    try:
        import onnxruntime as ort
        _onnx_session = ort.InferenceSession(RUTA_ONNX, providers=['CPUExecutionProvider'])
        print("✅ Modelo ONNX cargado correctamente.")
        return True
    except Exception as e:
        print(f"⚠️ No se pudo cargar ONNX: {e}")
        return False

def _init_tf():
    global _tf_model
    if not os.path.exists(RUTA_H5):
        return False
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import InputLayer, Dense, GlobalAveragePooling2D, RandomFlip, RandomRotation, Rescaling
        from tensorflow.keras.applications import MobileNetV2

        IMG_SHAPE = (IMG_SIZE, IMG_SIZE, 3)
        base_model = MobileNetV2(input_shape=IMG_SHAPE, include_top=False, weights=None)
        base_model.trainable = False
        model = Sequential([
            InputLayer(input_shape=IMG_SHAPE),
            Sequential([RandomFlip("horizontal_and_vertical"), RandomRotation(0.2)], name="aug"),
            Rescaling(1./127.5, offset=-1),
            base_model,
            GlobalAveragePooling2D(),
            Dense(128, activation='relu'),
            Dense(len(CLASS_NAMES), activation='softmax'),
        ])
        model(tf.zeros([1, IMG_SIZE, IMG_SIZE, 3]))
        model.load_weights(RUTA_H5)
        _tf_model = model
        print("✅ Modelo TensorFlow (.h5) cargado correctamente.")
        return True
    except Exception as e:
        print(f"⚠️ No se pudo cargar TensorFlow: {e}")
        return False

# Inicializar al importar el módulo — ONNX tiene prioridad
if not _init_onnx():
    _init_tf()


def _preprocess(img_pil):
    img = img_pil.convert('RGB').resize((IMG_SIZE, IMG_SIZE))
    arr = np.array(img, dtype=np.float32)
    return arr[np.newaxis, ...]   # shape (1, 224, 224, 3)


def procesar_prediccion(img_pil):
    global _onnx_session, _tf_model

    if _onnx_session is None and _tf_model is None:
        return {
            "error": "Modelo no disponible. Sube model/siembra_plus_doctor.onnx al repositorio.",
            "diagnostico": "Servicio no disponible",
            "descripcion": "El modelo de IA no se encontró en el servidor.",
            "id": -1,
            "status": "unavailable"
        }

    try:
        arr = _preprocess(img_pil)

        if _onnx_session is not None:
            import onnxruntime as ort
            input_name = _onnx_session.get_inputs()[0].name
            # ONNX espera valores normalizados [−1, 1] igual que el modelo original
            arr_norm = arr / 127.5 - 1.0
            preds = _onnx_session.run(None, {input_name: arr_norm})[0][0]
        else:
            import tensorflow as tf
            preds = _tf_model.predict(tf.expand_dims(arr, 0), verbose=0)[0]

        class_id = int(np.argmax(preds))
        class_name = CLASS_NAMES[class_id] if 0 <= class_id < len(CLASS_NAMES) else f"Desconocido (ID: {class_id})"
        descripcion = obtener_descripcion(class_name)

        return {"diagnostico": class_name, "descripcion": descripcion, "id": class_id, "status": "success"}

    except Exception as e:
        print(f"❌ Error durante la predicción: {e}")
        return {"diagnostico": "Error al analizar", "descripcion": "Error técnico al procesar la imagen.", "id": -1, "error": str(e), "status": "error"}
