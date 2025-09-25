from datetime import datetime, timedelta
from functools import wraps
from flask import current_app
import logging


CACHE_KEY = 'MATRICULAS_DATA'

logger = logging.getLogger(__name__)

def clear_matriculas_cache():
    """Limpia completamente la cache de matrículas"""
    try:
        current_app.config.pop('MATRICULAS_CACHE', None)
        logger.debug("Cache de matrículas limpiada")
    except Exception as e:
        logger.error(f"Error limpiando cache: {str(e)}")
        raise
        
        
def cache_matriculas_data(data):
    """Almacena datos de matrículas en cache con timeout"""
    current_app.config[CACHE_KEY] = {
        'data': data,
        'timestamp': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
    }

def get_cached_matriculas():
    """Obtiene matrículas desde cache si no han expirado"""
    cached = current_app.config.get(CACHE_KEY)
    if cached and datetime.fromisoformat(cached['expires_at']) > datetime.now():
        return cached['data']
    return None        


def matriculas_cache_decorator(func):
    """Decorador para cachear resultados de matrículas"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = f"matriculas_{kwargs.get('page',1)}_{kwargs.get('estado','')}_{kwargs.get('curso','')}"
        
        try:
            # Intentar obtener de cache
            cached = current_app.config.get('MATRICULAS_CACHE', {}).get(cache_key)
            if cached and datetime.now() < cached['expires']:
                logger.debug("Retornando matrículas desde cache")
                return cached['data']
                
            # Ejecutar función si no hay cache válida
            result = func(*args, **kwargs)
            
            # Guardar en cache
            cache_data = {
                'data': result,
                'expires': datetime.now() + timedelta(minutes=30)
            }
            current_app.config.setdefault('MATRICULAS_CACHE', {})[cache_key] = cache_data
            
            return result
            
        except Exception as e:
            logger.error(f"Error en cache decorator: {str(e)}")
            return func(*args, **kwargs)
            
    return wrapper    