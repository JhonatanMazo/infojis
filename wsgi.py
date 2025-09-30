import os
import sys

# Añadir el directorio 'backend' al path de Python para que encuentre el paquete 'app'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import create_app

# Crear la instancia de la aplicación para que Gunicorn la pueda usar
app = create_app()