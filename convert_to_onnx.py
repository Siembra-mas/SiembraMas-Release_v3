# Ejecutar en Google Colab o cualquier entorno con TensorFlow instalado:
#
#   from google.colab import files
#   files.upload()          # sube siembra_plus_doctor.h5
#   !python convert_to_onnx.py
#   files.download('siembra_plus_doctor.onnx')
#
# Luego coloca el .onnx en model/siembra_plus_doctor.onnx y haz commit+push.

import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    InputLayer, Dense, GlobalAveragePooling2D,
    RandomFlip, RandomRotation, Rescaling
)
from tensorflow.keras.applications import MobileNetV2
import tf2onnx

NUM_CLASSES = 38   # Ajusta si tu modelo tiene un número diferente de clases
IMG_SIZE    = 224
RUTA_H5     = "siembra_plus_doctor.h5"
RUTA_ONNX   = "siembra_plus_doctor.onnx"

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
    Dense(NUM_CLASSES, activation='softmax'),
])

model(tf.zeros([1, IMG_SIZE, IMG_SIZE, 3]))
model.load_weights(RUTA_H5)
print(f"✅ Pesos cargados desde {RUTA_H5}")

input_signature = [tf.TensorSpec([1, IMG_SIZE, IMG_SIZE, 3], tf.float32, name="input_1")]
onnx_model, _ = tf2onnx.convert.from_keras(model, input_signature=input_signature, opset=13)

with open(RUTA_ONNX, "wb") as f:
    f.write(onnx_model.SerializeToString())

print(f"✅ Modelo ONNX guardado en {RUTA_ONNX}")
print("   → Sube este archivo a model/siembra_plus_doctor.onnx en tu repositorio.")
