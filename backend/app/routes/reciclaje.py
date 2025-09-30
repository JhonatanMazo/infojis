from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models import User, Curso, Matricula, Asignacion, Inclusion, Asignatura, Periodo, Observacion, Pago, Boletin, Calificacion, Informe
from app import db
from sqlalchemy import extract
from app.utils.decorators import admin_required
from app.services.configuracion_service import get_active_config
from sqlalchemy import extract
from app.utils.file_uploads import remove_profile_picture


class SimplePagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total

    @property
    def pages(self):
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


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
    active_config = get_active_config()
    if not active_config or 'anio' not in active_config:
        flash('No hay un año lectivo configurado como activo.', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']

    tipo_filtro = request.args.get('tipo_modelo', 'todos')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    items_eliminados = {key: [] for key in MODELOS.keys()}
    
    if tipo_filtro != 'todos' and tipo_filtro in MODELOS:
        modelos_filtrados = {tipo_filtro: MODELOS[tipo_filtro]}
    else:
        modelos_filtrados = MODELOS

    for tipo_modelo, modelo in modelos_filtrados.items():
        query = modelo.query.filter_by(eliminado=True)

        # Lógica de filtrado por año lectivo
        if hasattr(modelo, 'año_lectivo'):
            # Modelos con relación directa al año lectivo (Matricula, Asignacion, Boletin)
            query = query.filter(modelo.año_lectivo == anio_lectivo)
        elif hasattr(modelo, 'anio_lectivo'):
             # Modelos con relación directa al año lectivo (Asignacion)
            query = query.filter(modelo.anio_lectivo == anio_lectivo)
        elif tipo_modelo in ['inclusion', 'observacion', 'pago']:
            # Modelos relacionados a través de Matricula
            query = query.join(Matricula).filter(Matricula.año_lectivo == anio_lectivo)
        elif hasattr(modelo, 'fecha_eliminacion'):
            # Modelos generales (Curso, Asignatura, Usuario, Periodo): filtrar por el año de eliminación
            query = query.filter(extract('year', modelo.fecha_eliminacion) == anio_lectivo)
        else:
            # Si un modelo no tiene cómo ser filtrado por año, se omite para evitar mostrar datos incorrectos.
            # Opcionalmente, podrías decidir mostrarlo siempre, pero eso iría contra el requisito.
            continue

        items = query.all()

        for item in items:
            user_name = "Desconocido"
            eliminado_por_id = getattr(item, 'eliminado_por', None)
            if eliminado_por_id:
                user = User.query.get(eliminado_por_id)
                if user:
                    # Tomar solo el primer nombre y primer apellido
                    primer_nombre = user.nombre.split()[0] if user.nombre else ""
                    primer_apellido = user.apellidos.split()[0] if user.apellidos else ""
                    user_name = f"{primer_nombre} {primer_apellido}".strip()

            fecha_eliminacion = getattr(item, 'fecha_eliminacion', None)
            items_eliminados[tipo_modelo].append((item, user_name, fecha_eliminacion))

    # Crear lista combinada para paginación
    elementos_combinados = []
    for tipo_modelo in MODELOS.keys():
        if tipo_filtro == 'todos' or tipo_filtro == tipo_modelo:
            for item_tuple in items_eliminados[tipo_modelo]:
                item, user_name, deletion_date = item_tuple
                elementos_combinados.append((tipo_modelo, item, user_name, deletion_date))

    # Aplicar paginación
    total = len(elementos_combinados)
    start = (page - 1) * per_page
    end = start + per_page
    elementos_paginados = elementos_combinados[start:end]

    # Crear objeto de paginación manual
    pagination = SimplePagination(elementos_paginados, page, per_page, total)

    return render_template('views/reciclaje.html',
                           elementos_pagination=pagination,
                           tipo_filtro=tipo_filtro,
                           anio_lectivo=anio_lectivo)

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
    active_config = get_active_config()
    if not active_config or 'anio' not in active_config:
        flash('No hay un año lectivo configurado como activo.', 'warning')
        return redirect(url_for('reciclaje.index'))
    
    anio_lectivo = active_config['anio']
    
    try:
        restaurados = 0
        items_a_restaurar = []
        for tipo_modelo, modelo in MODELOS.items():
            query = modelo.query.filter_by(eliminado=True)
            
            if hasattr(modelo, 'año_lectivo'):
                query = query.filter(modelo.año_lectivo == anio_lectivo)
            elif hasattr(modelo, 'anio_lectivo'):
                query = query.filter(modelo.anio_lectivo == anio_lectivo)
            elif tipo_modelo in ['inclusion', 'observacion', 'pago']:
                query = query.join(Matricula).filter(Matricula.año_lectivo == anio_lectivo)
            elif hasattr(modelo, 'fecha_eliminacion'):
                query = query.filter(extract('year', modelo.fecha_eliminacion) == anio_lectivo)
            else:
                continue
            
            items_a_restaurar.extend(query.all())

        
        for item in items_a_restaurar:
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
    active_config = get_active_config()
    if not active_config or 'anio' not in active_config:
        flash('No hay un año lectivo configurado como activo.', 'warning')
        return redirect(url_for('reciclaje.index'))
    
    anio_lectivo = active_config['anio']

    try:
        eliminados = 0
        items_a_eliminar_por_modelo = {}
        total_a_eliminar = 0

        for tipo_modelo, modelo in MODELOS.items():
            query = modelo.query.filter_by(eliminado=True)
            
            if hasattr(modelo, 'año_lectivo'):
                query = query.filter(modelo.año_lectivo == anio_lectivo)
            elif hasattr(modelo, 'anio_lectivo'):
                query = query.filter(modelo.anio_lectivo == anio_lectivo)
            elif tipo_modelo in ['inclusion', 'observacion', 'pago']:
                query = query.join(Matricula).filter(Matricula.año_lectivo == anio_lectivo)
            elif hasattr(modelo, 'fecha_eliminacion'):
                query = query.filter(extract('year', modelo.fecha_eliminacion) == anio_lectivo)
            else:
                continue
            
            items = query.all()
            if items:
                items_a_eliminar_por_modelo[tipo_modelo] = items
                total_a_eliminar += len(items)
        
        # Manejar periodos primero para evitar problemas de cascada
        if 'periodo' in items_a_eliminar_por_modelo:
            for periodo in items_a_eliminar_por_modelo['periodo']:
                Boletin.query.filter_by(id_periodo=periodo.id).delete()
                Calificacion.query.filter_by(id_periodo=periodo.id).delete()
                Asignacion.query.filter_by(id_periodo=periodo.id).delete()
                Informe.query.filter_by(id_periodo=periodo.id).delete()
                db.session.delete(periodo)
                eliminados += 1

        # Manejar otros modelos
        for tipo_modelo, items in items_a_eliminar_por_modelo.items():
            if tipo_modelo == 'periodo': continue
            
            for item in items:
                if tipo_modelo in ['usuario', 'matricula'] and item.foto:
                    remove_profile_picture(item.foto)
                db.session.delete(item)
                eliminados += 1

        db.session.commit()
        flash(f'{eliminados} elementos eliminados permanentemente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar elementos permanentemente: {str(e)}', 'danger')
    return redirect(url_for('reciclaje.index'))