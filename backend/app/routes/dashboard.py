from flask import render_template, Blueprint, session, flash, redirect, url_for
from app.utils.decorators import roles_required
from datetime import datetime, timedelta
from sqlalchemy import func, case
from app.models import Matricula, User, Asistencia, Inclusion, Curso, Asignatura, Asignacion, Periodo, AnioPeriodo, Actividad
from app import db
from app.services.configuracion_service import get_active_config
from flask_login import current_user

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@roles_required('admin', 'docente')
def index():
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))

    anio_lectivo = active_config.get('anio')

    periodo_actual = None
    if anio_lectivo:
        anio_periodo_actual = AnioPeriodo.query.filter_by(estado='activo', anio_lectivo=anio_lectivo).first()
        if anio_periodo_actual:
            periodo_actual = anio_periodo_actual.periodo

    base_query_matriculas = Matricula.query.filter_by(estado='activo')
    if anio_lectivo:
        base_query_matriculas = base_query_matriculas.filter(Matricula.año_lectivo == anio_lectivo)

    cursos_docente_ids = []
    total_cursos_asignados = 0
    nuevos_cursos_asignados = 0
    if current_user.rol == 'docente':
        asignaciones = Asignacion.query.filter_by(id_docente=current_user.id, anio_lectivo=anio_lectivo).all()
        cursos_docente_ids = [asig.id_curso for asig in asignaciones]
        base_query_matriculas = base_query_matriculas.filter(Matricula.id_curso.in_(cursos_docente_ids))
        total_cursos_asignados = len(set(cursos_docente_ids))
        
        nuevos_cursos_asignados = Asignacion.query.filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo',
            Asignacion.fecha_asignacion >= datetime.now() - timedelta(days=365)
        ).count()

    total_estudiantes = base_query_matriculas.count()
    nuevos_estudiantes = base_query_matriculas.filter(Matricula.fecha_matricula >= datetime.now() - timedelta(days=30)).count()
    
    total_docentes = User.query.filter_by(rol='docente', estado='activo').count()
    nuevos_docentes = User.query.filter(User.rol == 'docente', User.estado == 'activo', User.creado_en >= datetime.now() - timedelta(days=365)).count()

    hoy = datetime.now().date()
    ayer = hoy - timedelta(days=1)
    
    asistencia_base_query = (db.session.query(func.avg(case((Asistencia.estado == 'asistencia', 100), (Asistencia.estado == 'falta', 0), else_=50)))
                             .join(Matricula, Asistencia.id_matricula == Matricula.id)
                             .filter(Matricula.año_lectivo == anio_lectivo))
    if current_user.rol == 'docente':
        asignaciones_docente_ids = [asig.id for asig in Asignacion.query.filter_by(id_docente=current_user.id, estado='activo', anio_lectivo=anio_lectivo).all()]
        asistencia_base_query = asistencia_base_query.join(Asignacion, Asistencia.id_asignacion == Asignacion.id).filter(Asignacion.id.in_(asignaciones_docente_ids))

    # Consulta para contar asistencias
    asistencia_count_query = db.session.query(func.count(Asistencia.id)).join(Matricula, Asistencia.id_matricula == Matricula.id).filter(Matricula.año_lectivo == anio_lectivo)
    if current_user.rol == 'docente':
        asistencia_count_query = asistencia_count_query.join(Asignacion, Asistencia.id_asignacion == Asignacion.id).filter(Asignacion.id.in_(asignaciones_docente_ids))

    # Obtener periodo activo para filtrar asistencias
    start_date = None
    end_date = None
    if anio_lectivo:
        anio_periodo_activo = AnioPeriodo.query.filter_by(estado='activo', anio_lectivo=anio_lectivo).first()
        if anio_periodo_activo:
            periodo_inicio = anio_periodo_activo.fecha_inicio  # MM-DD
            periodo_fin = anio_periodo_activo.fecha_fin
            current_year = datetime.now().year
            start_date = datetime(current_year, int(periodo_inicio[:2]), int(periodo_inicio[3:]))
            end_date = datetime(current_year, int(periodo_fin[:2]), int(periodo_fin[3:]))
            if end_date < start_date:
                end_date = end_date.replace(year=current_year + 1)

    # Aplicar filtro de periodo activo a las consultas de asistencia
    if start_date and end_date:
        asistencia_base_query = asistencia_base_query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
        asistencia_count_query = asistencia_count_query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)

    asistencias_hoy_count = asistencia_count_query.filter(Asistencia.fecha == hoy).scalar() or 0
    asistencias_ayer_count = asistencia_count_query.filter(Asistencia.fecha == ayer).scalar() or 0

    # Mantener porcentaje para compatibilidad
    porcentaje_asistencia = round(asistencias_hoy_count, 1)
    tendencia_asistencia = round(asistencias_hoy_count - asistencias_ayer_count, 1)

    total_inclusiones = Inclusion.query.join(Matricula, Inclusion.id_matricula == Matricula.id).filter(Matricula.id.in_([m.id for m in base_query_matriculas.all()])).count()
    porcentaje_inclusion = round((total_inclusiones / total_estudiantes * 100), 1) if total_estudiantes else 0

    # Obtener los cursos que tienen matrículas activas en el año lectivo actual
    cursos_con_matriculas_ids_query = db.session.query(Matricula.id_curso).filter(
        Matricula.año_lectivo == anio_lectivo,
        Matricula.estado == 'activo'
    ).distinct()

    if current_user.rol == 'admin':
        cursos_con_matriculas_ids = [c[0] for c in cursos_con_matriculas_ids_query.all()]
    else: # rol docente
        cursos_con_matriculas_ids = [c[0] for c in cursos_con_matriculas_ids_query.filter(Matricula.id_curso.in_(cursos_docente_ids)).all()]

    # Obtener los objetos Curso, sin importar su estado 'activo' o 'inactivo'
    cursos = Curso.query.filter(Curso.id.in_(cursos_con_matriculas_ids)).order_by(Curso.nombre).all()
        
    cursos_nombres = [curso.nombre for curso in cursos]
    # Contar las matrículas para cada uno de esos cursos
    matriculas_por_curso = [base_query_matriculas.filter(Matricula.id_curso == curso.id).count() for curso in cursos]
    
    # Calcular semana actual (Lunes a Domingo)
    start_of_week = hoy - timedelta(days=hoy.weekday())  # Lunes de la semana actual
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    asistencia_semanal = []
    for i in range(7):  # Lunes a Domingo
        dia = start_of_week + timedelta(days=i)
        count = asistencia_count_query.filter(Asistencia.fecha == dia).scalar() or 0
        asistencia_semanal.append(count)
    
    if current_user.rol == 'admin':
        asignaturas = Asignatura.query.order_by(Asignatura.nombre).limit(6).all()
        docentes_por_asignatura = [Asignacion.query.filter_by(id_asignatura=asignatura.id, estado='activo', anio_lectivo=anio_lectivo).distinct(Asignacion.id_docente).count() for asignatura in asignaturas]
    else:
        asignaturas = Asignatura.query.join(Asignacion).filter(Asignacion.id_docente == current_user.id, Asignacion.estado == 'activo', Asignacion.anio_lectivo == anio_lectivo).distinct().order_by(Asignatura.nombre).limit(6).all()
        docentes_por_asignatura = [Asignacion.query.filter_by(id_docente=current_user.id, id_asignatura=asignatura.id, estado='activo', anio_lectivo=anio_lectivo).count() for asignatura in asignaturas]

    asignaturas_nombres = [asignatura.nombre for asignatura in asignaturas]

    # Obtener información de docentes para tooltips
    docentes_info = []
    for asignatura in asignaturas:
        if current_user.rol == 'admin':
            asignaciones = Asignacion.query.filter_by(id_asignatura=asignatura.id, estado='activo', anio_lectivo=anio_lectivo).all()
            docentes = []
            for asig in asignaciones:
                docente = User.query.get(asig.id_docente)
                curso = Curso.query.get(asig.id_curso)
                if docente:
                    docentes.append({
                        'nombre': f"{docente.nombre.split()[0] if docente.nombre else ''} {docente.apellidos.split()[0] if docente.apellidos else ''}".strip(),
                        'asignatura': asignatura.nombre,
                        'curso': curso.nombre if curso else ''
                    })
            docentes_info.append(docentes)
        else:
            asignaciones = Asignacion.query.filter_by(id_docente=current_user.id, id_asignatura=asignatura.id, estado='activo', anio_lectivo=anio_lectivo).all()
            docentes = []
            for asig in asignaciones:
                curso = Curso.query.get(asig.id_curso)
                docentes.append({
                    'nombre': f"{current_user.nombre.split()[0] if current_user.nombre else ''} {current_user.apellidos.split()[0] if current_user.apellidos else ''}".strip(),
                    'asignatura': asignatura.nombre,
                    'curso': curso.nombre if curso else ''
                })
            docentes_info.append(docentes)
    
    # Obtener actividades recientes
    leidas = session.get('notificaciones_leidas', [])
    leidas_ids = [n['id'] for n in leidas]

    # Unir con Asignacion para poder filtrar por año lectivo
    query = Actividad.query.join(Asignacion, Actividad.id_asignacion == Asignacion.id)

    # Filtrar por el año lectivo activo
    query = query.filter(Asignacion.anio_lectivo == anio_lectivo)

    # Todos los usuarios (admin y docentes) no ven las actividades que ellos mismos crearon
    query = query.filter(Actividad.creado_por != current_user.id)

    if current_user.rol == 'docente':
        # Para docentes, mostrar solo actividades de sus asignaciones en el año lectivo activo
        query = query.filter(Asignacion.id_docente == current_user.id)

    if leidas_ids:
        query = query.filter(Actividad.id.notin_(leidas_ids))
    
    actividades_recientes_query = query.order_by(Actividad.creado_en.desc()).limit(5).all()

    actividades_recientes = []
    for act in actividades_recientes_query:
        usuario = User.query.get(act.creado_por)
        actividades_recientes.append({
            'id': act.id,
            'tipo': act.tipo,
            'titulo': act.titulo,
            'detalle': act.detalle,
            'fecha': act.fecha,
            'creado_por': f'{usuario.nombre} {usuario.apellidos}' if usuario else 'Usuario',
        })

    if anio_lectivo:
        periodos_dropdown = db.session.query(Periodo).join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == anio_lectivo).order_by(Periodo.nombre.asc()).all()
    else:
        periodos_dropdown = []
    
    return render_template('views/dashboard.html',
        total_estudiantes=total_estudiantes,
        nuevos_estudiantes=nuevos_estudiantes,
        total_docentes=total_docentes,
        nuevos_docentes=nuevos_docentes,
        porcentaje_asistencia=porcentaje_asistencia,
        tendencia_asistencia=tendencia_asistencia,
        asistencias_hoy_count=asistencias_hoy_count,
        asistencias_ayer_count=asistencias_ayer_count,
        total_inclusiones=total_inclusiones,
        porcentaje_inclusion=porcentaje_inclusion,
        total_cursos_asignados=total_cursos_asignados,
        nuevos_cursos_asignados=nuevos_cursos_asignados,
        cursos_nombres=cursos_nombres,
        matriculas_por_curso=matriculas_por_curso,
        dias_semana=dias_semana,
        asistencia_semanal=asistencia_semanal,
        asignaturas_nombres=asignaturas_nombres,
        docentes_por_asignatura=docentes_por_asignatura,
        docentes_info=docentes_info,
        actividades_recientes=actividades_recientes,
        periodo_actual=periodo_actual,
        periodos=periodos_dropdown
    )