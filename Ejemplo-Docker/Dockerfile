# 1. Usamos una imagen oficial de Python como base (versión ligera)
FROM python:3.11-slim

# 2. Creamos y nos movemos a una carpeta de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiamos el archivo de dependencias a esa carpeta
COPY requirements.txt .

# 4. Instalamos las librerías necesarias
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos el resto de nuestro código local dentro del contenedor
COPY . .

# 6. El comando que se ejecutará por defecto al iniciar el contenedor
CMD ["python", "app.py"]
