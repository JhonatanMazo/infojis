from flask import current_app
from functools import wraps
from app.models.configuracion import SystemConfig
from datetime import datetime, timedelta
import json
import redis
from app import db
from app.services.asignacion_service import clear_asignaciones_cache
from app.services.matricula_service import clear_matriculas_cache

CACHE_KEY = 'ACTIVE_SYSTEM_CONFIG'

def clear_related_caches(func):
    """Decorador para limpiar caches relacionados después de operaciones de configuración"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            # Importar dentro de la función para evitar circular imports
            clear_asignaciones_cache()
            clear_matriculas_cache()
        except ImportError as e:
            current_app.logger.warning(f"No se pudieron limpiar caches relacionados: {e}")
        except Exception as e:
            current_app.logger.warning(f"Error al limpiar caches relacionados: {e}")
        return result
    return wrapper

def get_redis_connection():
    """Obtiene conexión a Redis con manejo de errores"""
    try:
        if not current_app.config.get('REDIS_ENABLED', False):
            return None
            
        return redis.Redis(
            host=current_app.config.get('REDIS_HOST', 'localhost'),
            port=current_app.config.get('REDIS_PORT', 6379),
            db=current_app.config.get('REDIS_DB', 0),
            password=current_app.config.get('REDIS_PASSWORD', None),
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
    except Exception as e:
        current_app.logger.error(f"Error al conectar con Redis: {e}")
        return None

def get_config_value(key, default=None):
    """Obtiene un valor específico de la configuración activa"""
    config = get_active_config()
    if not config:
        return default
    
    # Si config es un objeto SystemConfig
    if isinstance(config, SystemConfig):
        field_map = {
            'anio': 'anio',
            'id': 'id'
        }
        # Handle periodo_id and periodo_nombre separately as they come from AnioPeriodo
        if key == 'periodo_id':
            from app.models import AnioPeriodo # Import here to avoid circular dependency
            active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=config.anio, estado='activo').first()
            return active_anio_periodo.periodo_id if active_anio_periodo else default
        if key == 'periodo_nombre':
            from app.models import AnioPeriodo # Import here to avoid circular dependency
            active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=config.anio, estado='activo').first()
            return active_anio_periodo.periodo.nombre if active_anio_periodo and active_anio_periodo.periodo else default
        
        if key in field_map:
            field = field_map[key]
            if callable(field):
                return field(config)
            return getattr(config, field, default)
        return default
    
    # Si config es un diccionario (del cache)
    return config.get(key, default)

def get_active_config(return_object=False):
    """Obtiene la configuración activa desde redis o base de datos"""
    # Si se solicita el objeto completo, ir directamente a la BD
    if return_object:
        active_config_obj = SystemConfig.get_active_config()
        return active_config_obj
    
    # Primero intentar desde Redis si está disponible
    try:
        redis_conn = get_redis_connection()
        if redis_conn:
            cached_config = redis_conn.get(CACHE_KEY)
            if cached_config:
                config_data = json.loads(cached_config)
                # Convertir updated_at de string a datetime si existe
                if 'updated_at' in config_data and config_data['updated_at']:
                    config_data['updated_at'] = datetime.fromisoformat(config_data['updated_at'])
                return config_data
    except Exception as e:
        current_app.logger.error(f"Error al acceder a redis: {e}")
    
    # Si no hay en cache o hay error, cargar desde BD
    reloaded_config = reload_active_config()
    return reloaded_config

def reload_active_config():
    """Recarga la configuración activa en cache"""
    active_config = SystemConfig.get_active_config()
    if not active_config:
        clear_config_cache()
        return None
    
    # Solo almacenar datos serializables, no objetos SQLAlchemy
    config_data = {
        'id': active_config.id,
        'anio': active_config.anio,
        'updated_at': active_config.updated_at.isoformat() if active_config.updated_at else None
    }
    # Add active periodo_id and periodo_nombre from AnioPeriodo if available
    from app.models import AnioPeriodo # Import here to avoid circular dependency
    active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=active_config.anio, estado='activo').first()
    if active_anio_periodo:
        config_data['periodo_id'] = active_anio_periodo.periodo_id
        config_data['periodo_nombre'] = active_anio_periodo.periodo.nombre
    
    # Cachear en Redis si está disponible
    try:
        redis_conn = get_redis_connection()
        if redis_conn:
            redis_conn.setex(
                CACHE_KEY, 
                timedelta(hours=1), 
                json.dumps(config_data, default=str)
            )
    except Exception as e:
        current_app.logger.error(f"Error al guardar en Redis: {e}")
    
    return config_data

@clear_related_caches
def clear_config_cache():
    """Limpia la cache de configuración de Redis"""
    try:
        redis_conn = get_redis_connection()
        if redis_conn:
            redis_conn.delete(CACHE_KEY)
    except Exception as e:
        current_app.logger.error(f"Error al limpiar cache de Redis: {e}")

def get_active_year():
    """Obtiene el año activo actual"""
    config = get_active_config()
    if isinstance(config, SystemConfig):
        return config.anio
    elif isinstance(config, dict) and 'anio' in config:
        return config['anio']
    return None

def get_active_period_id():
    """Obtiene el ID del periodo activo actual"""
    config = get_active_config()
    if isinstance(config, dict) and 'periodo_id' in config:
        return config['periodo_id']
    # If config is a SystemConfig object (not from cache), or if 'periodo_id' is not in cache
    # we need to query AnioPeriodo directly
    from app.models import AnioPeriodo # Import here to avoid circular dependency
    active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=config.get('anio'), estado='activo').first()
    return active_anio_periodo.periodo_id if active_anio_periodo else None

def get_active_config_object():
    """Obtiene el objeto completo de configuración activa"""
    # Si no hay objeto en cache, cargar desde BD
    active_config = SystemConfig.get_active_config()
    if active_config:
        # Actualizar cache
        reload_active_config()
        return active_config
    
    return None

def is_config_active():
    """Verifica si hay una configuración activa"""
    return get_active_config() is not None

def get_config_for_year(anio):
    """Obtiene la configuración para un año específico"""
    try:
        redis_conn = get_redis_connection()
        cache_key = f"{CACHE_KEY}:{anio}"
        
        if redis_conn:
            cached_config = redis_conn.get(cache_key)
            if cached_config:
                return json.loads(cached_config)
        
        config = SystemConfig.get_by_year(anio)
        if not config:
            return None
            
        config_data = config.to_dict()
        
        if redis_conn:
            redis_conn.setex(
                cache_key,
                timedelta(hours=1),
                json.dumps(config_data, default=str)
            )
            
        return config_data
    except Exception as e:
        current_app.logger.error(f"Error al obtener configuración para año {anio}: {e}")
        return SystemConfig.get_by_year(anio)

@clear_related_caches
def set_active_config(anio):
    """Establece una configuración como activa y actualiza las caches"""
    try:
        # Obtener la configuración a activar con bloqueo para evitar condiciones de carrera
        config = SystemConfig.query.filter_by(anio=anio).with_for_update().first()
        if not config:
            current_app.logger.error(f"Intento de activar año no existente: {anio}")
            return None
            
        # Desactivar todas las configuraciones activas
        SystemConfig.query.filter_by(estado='activo').update({'estado': 'inactivo'})
        
        # Activar la configuración seleccionada
        config.estado = 'activo'
        config.updated_at = datetime.utcnow()
        
        # Recargar la configuración en cache
        reload_active_config()
        
        current_app.logger.info(f"Configuración activa cambiada al año: {anio}")
        return config
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al cambiar configuración activa: {e}")
        raise e
