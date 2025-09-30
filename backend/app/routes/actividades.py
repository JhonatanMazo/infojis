from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import current_user
from app.utils.decorators import roles_required
from datetime import datetime
from app.models import Actividad, User, Asignacion
from app import db
from app.services.configuracion_service import get_active_config
import logging
from functools import wraps

actividades_bp = Blueprint('actividades', __name__, url_prefix='/actividades')

def suppress_werkzeug_logs(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        werkzeug_logger = logging.getLogger('werkzeug')
        original_level = werkzeug_logger.level
        werkzeug_logger.setLevel(logging.ERROR)
        try:
            return f(*args, **kwargs)
        finally:
            werkzeug_logger.setLevel(original_level)
    return decorated_function

@actividades_bp.route('/eliminar/<int:id>', methods=['POST'])
@roles_required('admin', 'docente')
def eliminar_actividad(id):
    actividad = Actividad.query.get_or_404(id)
    db.session.delete(actividad)
    db.session.commit()
    flash('Notificación eliminada permanentemente.', 'success')
    return redirect(url_for('actividades.index'))

@actividades_bp.route('/eliminar-todas', methods=['POST'])
@roles_required('admin', 'docente')
def eliminar_todas_actividades():
    leidas = session.get('notificaciones_leidas', [])
    
    # Obtener todas las actividades no leídas y no creadas por el usuario actual
    actividades_a_marcar = Actividad.query.filter(Actividad.creado_por != current_user.id).all()
    
    for act in actividades_a_marcar:
        notificacion = {'tipo': act.tipo, 'id': act.id}
        if notificacion not in leidas:
            leidas.append(notificacion)
            
    session['notificaciones_leidas'] = leidas
    flash('Todas las notificaciones han sido marcadas como leídas.', 'success')
    return redirect(url_for('actividades.index'))


@actividades_bp.route('/')
@roles_required('admin', 'docente')
def index():
    # Marcar el tiempo de la visita para resetear el contador de notificaciones
    session['notificaciones_vistas_hasta'] = datetime.utcnow().isoformat()
    
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))

    anio_lectivo = active_config['anio']
    
    leidas = session.get('notificaciones_leidas', [])
    leidas_ids = [n['id'] for n in leidas]

    # Filtros opcionales
    tipo = request.args.get('tipo')
    fecha_str = request.args.get('fecha')

    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Query base
    # Unir con Asignacion para poder filtrar por año lectivo
    query = Actividad.query.join(Asignacion, Actividad.id_asignacion == Asignacion.id)

    # Filtrar por el año lectivo activo
    query = query.filter(Asignacion.anio_lectivo == anio_lectivo)

    # Filtro adicional basado en el rol del usuario
    if hasattr(current_user, 'rol') and current_user.rol == 'docente':
        # Para docentes, mostrar solo actividades de sus asignaciones
        query = query.filter(Asignacion.id_docente == current_user.id)
    
    # Todos los usuarios (admin y docentes) no ven las actividades que ellos mismos crearon
    query = query.filter(Actividad.creado_por != current_user.id)

    # Aplicar filtros de fecha
    if fecha_str:
        try:
            fecha_para_filtrar = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            query = query.filter(Actividad.fecha == fecha_para_filtrar)
        except (ValueError, TypeError):
            flash('Formato de fecha inválido.', 'warning')
    
    # Aplicar filtro de tipo
    if tipo:
        query = query.filter(Actividad.tipo == tipo)

    total_actividades = query.count()

    # Aplicar filtro de notificaciones leídas
    if leidas_ids:
        query = query.filter(Actividad.id.notin_(leidas_ids))

    # Ordenar y ejecutar la consulta con paginación
    pagination = query.order_by(Actividad.creado_en.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    total_visibles = pagination.total

    # Adjuntar nombre del usuario que creó la actividad
    actividades_data = []
    for act in pagination.items:
        usuario = User.query.get(act.creado_por)
        actividades_data.append({
            'id': act.id,
            'tipo': act.tipo,
            'titulo': act.titulo,
            'detalle': act.detalle,
            'fecha': act.fecha,
            'creado_por': f'{usuario.nombre} {usuario.apellidos}' if usuario else 'Usuario',
        })

    return render_template('views/actividades.html',
                           actividades=actividades_data,
                           tipo=tipo,
                           fecha=fecha_str,
                           pagination=pagination,
                           total_visibles=total_visibles,
                           total_actividades=total_actividades,
                           anio_lectivo=anio_lectivo)

@actividades_bp.route('/count_unread_notifications')
@roles_required('admin', 'docente')
@suppress_werkzeug_logs
def count_unread_notifications():
    if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
        return jsonify({'count': 0}), 200

    # Para evitar logs repetidos, solo loguear la primera vez en la sesión
    if 'count_logged' not in session:
        session['count_logged'] = True
        logging.getLogger('werkzeug').info(f"Count unread notifications requested by user {current_user.id}")

    # Timestamp de la última vez que el usuario vio las notificaciones
    vistas_hasta_str = session.get('notificaciones_vistas_hasta')
    if vistas_hasta_str:
        vistas_hasta = datetime.fromisoformat(vistas_hasta_str)
    else:
        # Si no hay timestamp, no hay notificaciones nuevas que contar para la sesión actual
        vistas_hasta = datetime.utcnow()

    # Notificaciones ocultas/eliminadas por el usuario
    ocultas = session.get('notificaciones_leidas', [])
    ocultas_ids = [n['id'] for n in ocultas]

    # Query base
    # Unir con Asignacion para poder filtrar por año lectivo
    query = Actividad.query.join(Asignacion, Actividad.id_asignacion == Asignacion.id)

    # Filtrar por el año lectivo activo
    active_config = get_active_config()
    if active_config and 'anio' in active_config:
        query = query.filter(Asignacion.anio_lectivo == active_config['anio'])

    # Filtro basado en el rol del usuario
    if hasattr(current_user, 'rol') and current_user.rol == 'docente':
        query = query.filter(Asignacion.id_docente == current_user.id)
        
    # Filtros comunes
    query = query.filter(
        Actividad.creado_por != current_user.id,
        Actividad.creado_en > vistas_hasta
    )

    if ocultas_ids:
        query = query.filter(Actividad.id.notin_(ocultas_ids))
    
    count = query.count()
    
    return jsonify({'count': count}), 200