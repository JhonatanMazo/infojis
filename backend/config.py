import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Configuración de rutas base
    BASE_DIR = Path(__file__).resolve().parent.parent
    FRONTEND_DIR = BASE_DIR / 'frontend'
    BACKEND_DIR = BASE_DIR / 'backend'

    USER_ALLOWED_ROLES = ['admin', 'docente']

    # 2. Configuración de rutas
    TEMPLATES_PATH = str(FRONTEND_DIR / 'templates')
    STATIC_PATH = str(FRONTEND_DIR / 'static')
    UPLOAD_FOLDER = str(FRONTEND_DIR / 'static' / 'uploads')
    
    # 3. Configuración esencial
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-segura-123")
    
    # 4. Base de datos
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", f"sqlite:///{BACKEND_DIR}/app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true"
    
    # 5. Configuración de seguridad
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    WTF_CSRF_ENABLED = True

    # 6. Configuración CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")

    # 7. Configuración Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7) 
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)  # Tiempo máximo hasta un cierre de sesión forzado
    MAX_FAILED_ATTEMPTS = 3  # Número de intentos fallidos para desactivar al usuario

    # 8. Configuración de desarrollo
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    TEMPLATES_AUTO_RELOAD = True if DEBUG else False

    # 9. Subcarpetas para uploads
    UPLOAD_SUBFOLDERS = {
        'profiles': 'profiles',
        'documents': 'documents'
    }
    
    # 10. Configuración de archivos
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

    # 11. Configuración de envio de email
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_TIMEOUT = int(os.getenv("MAIL_TIMEOUT", 60))  # segundos
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", None)
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", None)
    MAIL_DEFAULT_SENDER = ("Infojis Admin", MAIL_USERNAME)
    MAIL_DEBUG = False
    



    

    @classmethod
    def init_app(cls, app):
        """Inicialización adicional para la aplicación"""
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        for folder in cls.UPLOAD_SUBFOLDERS.values():
            os.makedirs(os.path.join(cls.UPLOAD_FOLDER, folder), exist_ok=True)

    @classmethod
    def verify_paths(cls):
        """Verifica que las rutas críticas existan"""
        required_paths = [
            cls.TEMPLATES_PATH,
            cls.STATIC_PATH,
            cls.UPLOAD_FOLDER
        ]
        
        for path in required_paths:
            if not os.path.exists(path):
                raise RuntimeError(f"Ruta crítica no encontrada: {path}")