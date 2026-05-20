FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema requeridas por TensorFlow, Pillow y audio
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (aprovecha cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

# Render asigna el puerto vía variable PORT; gunicorn lo lee de ahí
EXPOSE 10000

CMD gunicorn app:app --workers 2 --timeout 120 --bind 0.0.0.0:${PORT:-10000}
