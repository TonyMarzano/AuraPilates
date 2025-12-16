from flask import Flask, render_template

# Inicialización de la aplicación
app = Flask(__name__)

# Definición de la ruta principal
@app.route('/')
def index():
    # Datos de contacto que se pasan a la plantilla HTML
    contact_data = {
        "whatsapp_link": "https://wa.me/5492645551234",
        "email": "info@aurapilates.com.ar",
        "address": "San Roque Sur 1044, Rawson, San Juan",
        # La clave de API de Google Maps se debe gestionar de forma segura
        "google_maps_api_key": "TU_API_KEY_AQUI" 
    }
    return render_template('index.html', data=contact_data)

# Ejecución del servidor
if __name__ == '__main__':
    # Nota: En producción (EC2), usarías Gunicorn, no el servidor de desarrollo de Flask
    app.run(debug=True)
