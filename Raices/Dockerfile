# Imagen para Cloud Run (o cualquier contenedor). No hace falta Nginx: Cloud Run ya termina HTTPS.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY SRC/ ./SRC/
WORKDIR /app/SRC
ENV RAICES_ENV=production PROXY_SALTOS=1 PORT=8080
# Cloud Run envía las peticiones al puerto de $PORT. 2 hilos bastan para el tráfico esperado.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 60 "app:create_app()"
