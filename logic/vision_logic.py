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
RUTA_H5 = os.path.join(project_root, 'model', 'siembra_plus_doctor.h5')

_model_instance = None

def _cargar_modelo():
    global _model_instance
    if _model_instance is not None:
        return _model_instance
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import (
            InputLayer, Dense, GlobalAveragePooling2D,
            RandomFlip, RandomRotation, Rescaling
        )
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
        _model_instance = model
        print("✅ Modelo TensorFlow cargado.")
        return _model_instance
    except Exception as e:
        print(f"❌ Error cargando modelo: {e}")
        return None


def procesar_prediccion(img_pil):
    model = _cargar_modelo()

    if model is None:
        return {
            "error": "Modelo no disponible.",
            "diagnostico": "Servicio no disponible",
            "descripcion": "No se pudo cargar el modelo de IA en este servidor.",
            "id": -1,
            "status": "unavailable"
        }

    try:
        import tensorflow as tf
        img = img_pil.convert('RGB').resize((IMG_SIZE, IMG_SIZE))
        arr = np.array(img, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.stack([arr]*3, axis=-1)
        tensor = tf.expand_dims(arr, 0)

        preds = model.predict(tensor, verbose=0)
        class_id = int(np.argmax(preds[0]))
        class_name = CLASS_NAMES[class_id] if 0 <= class_id < len(CLASS_NAMES) else f"Desconocido (ID: {class_id})"
        descripcion = obtener_descripcion(class_name)

        return {"diagnostico": class_name, "descripcion": descripcion, "id": class_id, "status": "success"}

    except Exception as e:
        print(f"❌ Error en predicción: {e}")
        return {"diagnostico": "Error al analizar", "descripcion": "Error técnico.", "id": -1, "error": str(e), "status": "error"}
