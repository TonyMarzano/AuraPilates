# Imagen base con Python 3.10
FROM python:3.10-slim

# Evita que Python genere archivos pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de la aplicación
WORKDIR /app

# Copia requirements y los instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código
COPY . .

# Expone el puerto que usará Flask
EXPOSE 5000

# Comando para iniciar la app con Gunicorn (recomendado)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
