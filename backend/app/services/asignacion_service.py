from flask import current_app
from datetime import datetime
from app.models.configuracion import SystemConfig

    
def get_asignaciones_cache(anio_lectivo, page=None, curso_id=None):
    """Obtiene asignaciones desde cache con validación y filtros opcionales"""
    # Construir clave de cache
    cache_key = f'ASIGNACIONES_CACHE_{anio_lectivo}'
    if page is not None:
        cache_key += f'_page_{page}'
    if curso_id is not None:
        cache_key += f'_curso_{curso_id}'
    
    cached_data = current_app.config.get(cache_key)
    
    if cached_data:
        from app.services.configuracion_service import get_active_config
        active_config = get_active_config()

        if active_config and active_config['anio'] == anio_lectivo:
            config = SystemConfig.query.filter_by(anio=anio_lectivo).first()
            if config and 'cache_timestamp' in cached_data and cached_data['cache_timestamp'] >= config.updated_at:
                return cached_data['data']
    
    return None
    


def set_asignaciones_cache(anio_lectivo, page=None, curso_id=None, data=None):
    """Guarda asignaciones en cache con filtros específicos"""
    # Construir clave de cache (igual que en get)
    cache_key = f'ASIGNACIONES_CACHE_{anio_lectivo}'
    if page is not None:
        cache_key += f'_page_{page}'
    if curso_id is not None:
        cache_key += f'_curso_{curso_id}'
    
    config = SystemConfig.query.filter_by(anio=anio_lectivo).first()
    
    if config and data is not None:
        current_app.config[cache_key] = {
            'data': data,
            'cache_timestamp': datetime.utcnow(),
            'config_version': config.updated_at
        }
        

def clear_asignaciones_cache(anio_lectivo=None):
    """Limpia la cache de asignaciones para un año específico o toda la cache"""
    if anio_lectivo:
        current_app.config.pop(f'ASIGNACIONES_CACHE_{anio_lectivo}', None)
    else:
        # Limpiar toda la cache de asignaciones
        for key in list(current_app.config.keys()):
            if key.startswith('ASIGNACIONES_CACHE_'):
                current_app.config.pop(key, None)