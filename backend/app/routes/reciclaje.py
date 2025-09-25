from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import User, Curso, Matricula, Asignacion, Inclusion, Asignatura, Periodo, Observacion, Pago, Boletin, Calificacion, Informe
from app import db
from app.utils.decorators import admin_required
from app.services.configuracion_service import get_active_config
from app.utils.file_uploads import remove_profile_picture


reciclaje_bp = Blueprint('reciclaje', __name__, url_prefix='/reciclaje')

# Mapeo de modelos para simplificar las operaciones
MODELOS = {
    'usuario': User,
    'curso': Curso,
    'matricula': Matricula,
    'asignacion': Asignacion,
    'inclusion': Inclusion,
    'asignatura': Asignatura,
    'periodo': Periodo,
    'observacion': Observacion,
    'pago': Pago,
    'boletin': Boletin # Añadir Boletin al mapeo
}

@reciclaje_bp.route('/')
@admin_required
def index():
    tipo_filtro = request.args.get('tipo_modelo', 'todos')
    items_eliminados = {key: [] for key in MODELOS.keys()}
    if tipo_filtro != 'todos' and tipo_filtro in MODELOS:
        modelos_filtrados = {tipo_filtro: MODELOS[tipo_filtro]}
    else:
        modelos_filtrados = MODELOS
    for tipo_modelo, modelo in modelos_filtrados.items():
        items = modelo.query.filter_by(eliminado=True).all()
        for item in items:
            # Obtener usuario y fecha directamente del modelo
            user = User.query.get(getattr(item, 'eliminado_por', None))
            user_name = f"{user.nombre} {user.apellidos}" if user else "Desconocido"
            deletion_date = getattr(item, 'fecha_eliminacion', None)
            items_eliminados[tipo_modelo].append((item, user_name, deletion_date))
            
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    return render_template('views/reciclaje.html', 
                           usuarios_eliminados=items_eliminados.get('usuario', []),
                           cursos_eliminados=items_eliminados.get('curso', []),
                           matriculas_eliminadas=items_eliminados.get('matricula', []),
                           asignaciones_eliminadas=items_eliminados.get('asignacion', []),
                           inclusiones_eliminadas=items_eliminados.get('inclusion', []),
                           asignaturas_eliminadas=items_eliminados.get('asignatura', []),
                           periodos_eliminados=items_eliminados.get('periodo', []),
                           observaciones_eliminadas=items_eliminados.get('observacion', []),
                           pagos_eliminados=items_eliminados.get('pago', []),
                           boletines_eliminados=items_eliminados.get('boletin', []),
                           tipo_filtro=tipo_filtro)

@reciclaje_bp.route('/restaurar/<string:tipo_modelo>/<int:item_id>', methods=['POST'])
@admin_required
def restaurar_item(tipo_modelo, item_id):
    modelo = MODELOS.get(tipo_modelo)
    if not modelo:
        flash('Tipo de elemento no válido.', 'danger')
        return redirect(url_for('reciclaje.index'))

    item = modelo.query.get_or_404(item_id)
    
    if hasattr(item, 'eliminado'):
        item.eliminado = False
        item.fecha_eliminacion = None
    elif hasattr(item, 'estado'):
        item.estado = 'activo'
    
    db.session.commit()
    flash(f'{tipo_modelo.capitalize()} restaurado correctamente.', 'success')
    return redirect(url_for('reciclaje.index'))

@reciclaje_bp.route('/eliminar_definitivo/<string:tipo_modelo>/<int:item_id>', methods=['POST'])
@admin_required
def eliminar_definitivo_item(tipo_modelo, item_id):
    modelo = MODELOS.get(tipo_modelo)
    if not modelo:
        flash('Tipo de elemento no válido.', 'danger')
        return redirect(url_for('reciclaje.index'))

    item = modelo.query.get_or_404(item_id)

    if tipo_modelo == 'usuario' and item.foto:
        
        remove_profile_picture(item.foto)
    elif tipo_modelo == 'matricula' and item.foto:
        remove_profile_picture(item.foto)

    # Handle cascade delete for periodo related models
    if tipo_modelo == 'periodo':
        # Delete related boletines, calificaciones, asignaciones, informes explicitly
        boletines = Boletin.query.filter_by(id_periodo=item.id).all()
        for b in boletines:
            db.session.delete(b)
        calificaciones = Calificacion.query.filter_by(id_periodo=item.id).all()
        for c in calificaciones:
            db.session.delete(c)
        asignaciones = Asignacion.query.filter_by(id_periodo=item.id).all()
        for a in asignaciones:
            db.session.delete(a)
        informes = Informe.query.filter_by(id_periodo=item.id).all()
        for i in informes:
            db.session.delete(i)

    db.session.delete(item)
    db.session.commit()
    flash(f'{tipo_modelo.capitalize()} eliminado permanentemente.', 'success')
    return redirect(url_for('reciclaje.index'))

@reciclaje_bp.route('/restaurar_todo', methods=['POST'])
@admin_required
def restaurar_todo():
    try:
        restaurados = 0
        for tipo_modelo, modelo in MODELOS.items():
            items = modelo.query.filter_by(eliminado=True).all()
            for item in items:
                if hasattr(item, 'eliminado'):
                    item.eliminado = False
                    if hasattr(item, 'fecha_eliminacion'):
                        item.fecha_eliminacion = None
                    restaurados += 1
                elif hasattr(item, 'estado'):
                    item.estado = 'activo'
                    restaurados += 1
        db.session.commit()
        flash(f'{restaurados} elementos restaurados correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al restaurar elementos: {str(e)}', 'danger')
    return redirect(url_for('reciclaje.index'))

@reciclaje_bp.route('/eliminar_todo_definitivo', methods=['POST'])
@admin_required
def eliminar_todo_definitivo():
    try:
        eliminados = 0
        # Handle periodos first to avoid cascade issues
        periodos = Periodo.query.filter_by(eliminado=True).all()
        for periodo in periodos:
            # Delete related records first
            boletines = Boletin.query.filter_by(id_periodo=periodo.id).all()
            for b in boletines:
                db.session.delete(b)
            calificaciones = Calificacion.query.filter_by(id_periodo=periodo.id).all()
            for c in calificaciones:
                db.session.delete(c)
            asignaciones = Asignacion.query.filter_by(id_periodo=periodo.id).all()
            for a in asignaciones:
                db.session.delete(a)
            informes = Informe.query.filter_by(id_periodo=periodo.id).all()
            for i in informes:
                db.session.delete(i)
            db.session.delete(periodo)
            eliminados += 1

        # Handle other models
        for tipo_modelo, modelo in MODELOS.items():
            if tipo_modelo == 'periodo':
                continue  # Already handled above
            items = modelo.query.filter_by(eliminado=True).all()
            for item in items:
                if tipo_modelo == 'usuario' and item.foto:
                    from app.utils.file_uploads import remove_profile_picture
                    remove_profile_picture(item.foto)
                elif tipo_modelo == 'matricula' and item.foto:
                    from app.utils.file_uploads import remove_profile_picture
                    remove_profile_picture(item.foto)
                db.session.delete(item)
                eliminados += 1
        db.session.commit()
        flash(f'{eliminados} elementos eliminados permanentemente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar elementos permanentemente: {str(e)}', 'danger')
    return redirect(url_for('reciclaje.index'))
