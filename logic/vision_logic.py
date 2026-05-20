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

IMG_SIZE    = 224
CLASS_NAMES = clase
RUTA_ONNX   = os.path.join(project_root, 'model', 'siembra_plus_doctor.onnx')

_session = None

def _cargar_sesion():
    global _session
    if _session is not None:
        return _session
    if not os.path.exists(RUTA_ONNX):
        print(f"❌ No se encontró el modelo ONNX en: {RUTA_ONNX}")
        return None
    try:
        import onnxruntime as ort
        _session = ort.InferenceSession(RUTA_ONNX, providers=['CPUExecutionProvider'])
        print("✅ Modelo ONNX cargado correctamente.")
        return _session
    except Exception as e:
        print(f"❌ Error cargando ONNX: {e}")
        return None


def procesar_prediccion(img_pil):
    session = _cargar_sesion()

    if session is None:
        return {
            "error": "Modelo no disponible. Falta model/siembra_plus_doctor.onnx",
            "diagnostico": "Servicio no disponible",
            "descripcion": "El modelo de IA no se encontró. Contacta al administrador.",
            "id": -1,
            "status": "unavailable"
        }

    try:
        img = img_pil.convert('RGB').resize((IMG_SIZE, IMG_SIZE))
        arr = np.array(img, dtype=np.float32)
        # Normalizar igual que el modelo original (Rescaling 1/127.5 − 1)
        arr = arr / 127.5 - 1.0
        arr = arr[np.newaxis, ...]   # (1, 224, 224, 3)

        input_name = session.get_inputs()[0].name
        preds = session.run(None, {input_name: arr})[0][0]

        class_id  = int(np.argmax(preds))
        class_name = CLASS_NAMES[class_id] if 0 <= class_id < len(CLASS_NAMES) else f"Desconocido (ID: {class_id})"
        descripcion = obtener_descripcion(class_name)

        return {"diagnostico": class_name, "descripcion": descripcion, "id": class_id, "status": "success"}

    except Exception as e:
        print(f"❌ Error en predicción: {e}")
        return {"diagnostico": "Error al analizar", "descripcion": "Error técnico al procesar la imagen.", "id": -1, "error": str(e), "status": "error"}
