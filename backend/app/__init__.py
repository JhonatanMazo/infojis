import logging
from flask import Flask, current_app, render_template, flash, redirect, url_for
from app.extensions import db, login_manager, migrate, csrf, mail
from flask_cors import CORS
from config import Config
import pymysql
pymysql.install_as_MySQLdb()
from datetime import datetime, timedelta
from app.models import Actividad, User, Asignacion
from flask import session
from flask_login import current_user, logout_user
from app.routes import register_blueprints
from sqlalchemy import or_
from app.services.configuracion_service import reload_active_config

def timeago_filter(dt):
    now = datetime.utcnow()
    # Si dt es date, conviértelo a datetime
    if hasattr(dt, 'year') and not hasattr(dt, 'hour'):
        dt = datetime(dt.year, dt.month, dt.day)
    diff = now - dt

    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = diff.days

    if seconds < 60:
        return "hace unos segundos"
    elif minutes < 60:
        return f"hace {int(minutes)} minutos"
    elif hours < 24:
        return f"hace {int(hours)} horas"
    elif days < 30:
        return f"hace {int(days)} días"
    else:
        return dt.strftime("%d/%m/%Y")

def load_system_config():
    """
    Carga la configuración inicial del sistema.
    Esta función se ejecuta al iniciar la aplicación.
    """
    try:
        reload_active_config()
        print("[OK] Configuracion del sistema cargada exitosamente")
    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo cargar la configuracion del sistema: {e}")

def create_app(config_class=Config):

    # Crear aplicación Flask con rutas de template y static desde frontend
    app = Flask(
        __name__,
        template_folder=str(config_class.FRONTEND_DIR / 'templates'),
        static_folder=str(config_class.FRONTEND_DIR / 'static')
    )

    @app.context_processor
    def inject_notificaciones_hoy():
        notificaciones_count = 0
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            
            # Timestamp de la última vez que el usuario vio las notificaciones
            vistas_hasta_str = session.get('notificaciones_vistas_hasta')
            if vistas_hasta_str:
                vistas_hasta = datetime.fromisoformat(vistas_hasta_str)
            else:
                # Si nunca ha visitado la página, mostramos notificaciones de las últimas 24 horas
                vistas_hasta = datetime.utcnow() - timedelta(days=1)

            # Notificaciones ocultas/eliminadas por el usuario
            ocultas = session.get('notificaciones_leidas', [])
            ocultas_ids = [n['id'] for n in ocultas]

            # Contar actividades nuevas desde la última visita, que no estén ocultas
            query = (
                Actividad.query
                .filter(Actividad.creado_por != current_user.id)
                .filter(Actividad.creado_en > vistas_hasta)
            )

            if current_user.rol == 'docente':
                asignaciones_docente_ids = [asig.id for asig in Asignacion.query.filter_by(id_docente=current_user.id).all()]
                query = query.filter(
                    or_(
                        Actividad.id_asignacion.in_(asignaciones_docente_ids),
                        Actividad.id_asignacion == None
                    )
                )

            if ocultas_ids:
                query = query.filter(Actividad.id.notin_(ocultas_ids))
            
            notificaciones_count = query.count()

        return dict(notificaciones_hoy=notificaciones_count)
    # (Ya se creó la instancia app arriba, no repetir)
    
    # Cargar configuración
    app.config.from_object(config_class)
    config_class.init_app(app)
    config_class.verify_paths()

    # Iniciar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app) 

    # Registra el filtro en Jinja2
    app.jinja_env.filters['timeago'] = timeago_filter

    # Configuración de Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @app.before_request
    def check_security_stamp():
        if current_user.is_authenticated:
            current_app.logger.debug(f"DEBUG: Before request - Current user ID: {current_user.id}")
            current_app.logger.debug(f"DEBUG: Before request - Session security stamp: {session.get('security_stamp')}")
            current_app.logger.debug(f"DEBUG: Before request - User object security stamp: {current_user.security_stamp}")

            if 'security_stamp' in session and session['security_stamp'] != current_user.security_stamp:
                current_app.logger.debug(f"DEBUG: Before request - Security stamp mismatch detected for user {current_user.id}. Logging out.")
                logout_user()
                flash('Su credencial ha sido desactivada', 'warning')
                return redirect(url_for('auth.login'))
        else:
            current_app.logger.debug("DEBUG: Before request - User is not authenticated.")

    # Registro de user_loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        current_app.logger.debug(f"DEBUG: load_user called for user_id: {user_id}")
        user = User.query.get(int(user_id))
        if user:
            current_app.logger.debug(f"DEBUG: load_user - User {user.id} found. DB security stamp: {user.security_stamp}")
        else:
            current_app.logger.debug(f"DEBUG: load_user - User {user_id} not found in DB.")
        return user

    # CORS y CSRF
    CORS(app, resources={r"/*": {"origins": app.config['CORS_ORIGINS']}})
    csrf.init_app(app)

    # Registrar blueprints
    register_blueprints(app)

    # Filtrar logs de acceso para la ruta específica
    class NoAccessLogFilter(logging.Filter):
        def filter(self, record):
            return '/actividades/count_unread_notifications' not in record.getMessage()

    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(NoAccessLogFilter())

    # Cargar configuración del sistema dentro del contexto de la aplicación
    with app.app_context():
        load_system_config()

    # Manejadores de error
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

# Entry point para CLI o ejecución directa
if __name__ == '__main__':
    app = create_app()
    app.run(debug=app.config['DEBUG'])