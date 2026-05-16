import requests

print("¡Hola desde un contenedor Docker!")
response = requests.get("https://api.github.com")
print(f"Estado de la conexión a GitHub: {response.status_code}")
