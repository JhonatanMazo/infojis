from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import current_user
from sqlalchemy import func
from app import db, mail
from app.models import Boletin, Matricula, Periodo, Curso, Calificacion, Asignatura, Asignacion, ConfiguracionLibro, AnioPeriodo, Asistencia
from app.models.configuracion import RectorConfig 
from app.utils.decorators import roles_required
from io import BytesIO
from reportlab.lib.pagesizes import letter
from app.services.configuracion_service import get_active_config
import json
from sqlalchemy import or_
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor, black
from flask_mail import Message
from datetime import datetime
import os
import zipfile

boletines_bp = Blueprint('boletines', __name__, url_prefix='/boletines')

def obtener_datos_rector():
    config = RectorConfig.query.first()
    if config:
        return config.nombre or '', config.identidad or '', config.firma_url or None
    return '', '', None

def get_desempeno(nota):
    if nota is None:
        return ''
    
    config = ConfiguracionLibro.obtener_configuracion_actual()
    
    if nota >= config.nota_superior:
        return 'Superior'
    elif nota >= config.nota_alto:
        return 'Alto'
    elif nota >= config.nota_basico:
        return 'Básico'
    else:
        return 'Bajo'

@boletines_bp.route('/api/boletines/asignaturas')
@roles_required('admin', 'docente')
def api_boletines_asignaturas():
    estudiante_id = request.args.get('estudiante_id', type=int)
    curso_id = request.args.get('curso_id', type=int)
    
    if not estudiante_id and not curso_id:
        return jsonify({'error': 'Faltan parámetros'}), 400

    # Obtener año lectivo activo
    active_config = get_active_config()
    if not active_config:
        return jsonify({'error': 'No hay un año lectivo configurado como activo'}), 400
    
    anio_lectivo = active_config['anio']

    asignaturas = []
    calificaciones = {}
    if estudiante_id:
        matricula = Matricula.query.filter_by(id=estudiante_id, estado='activo', año_lectivo=anio_lectivo).first()
        if not matricula:
            return jsonify([])
        curso_id = matricula.id_curso
        asignaturas = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).all()
        
        # Calcular el promedio de calificaciones por asignatura para el estudiante en el AÑO LECTIVO
        calificaciones_avg = db.session.query(
            Asignacion.id_asignatura,
            func.avg(Calificacion.nota).label('promedio')
        ).join(Calificacion, Asignacion.id == Calificacion.id_asignacion).filter(
            Calificacion.id_matricula == matricula.id,
            Asignacion.anio_lectivo == anio_lectivo
        ).group_by(Asignacion.id_asignatura).all()

        calificaciones = {id_asig: round(prom, 2) if prom is not None else None for id_asig, prom in calificaciones_avg}

    elif curso_id:
        asignaturas = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).all()
        
        resultado = []
        for asig in asignaturas:
            resultado.append({
                'id': asig.id,
                'area': asig.area if hasattr(asig, 'area') else '',
                'nombre': asig.nombre,
                'nota': '',
                'desempeno': '',
                'observaciones_pasadas': []
            })
        return jsonify(resultado)

    resultado = []
    for asig in asignaturas:
        nota = calificaciones.get(asig.id)
        desempeno = get_desempeno(nota)
        resultado.append({
            'id': asig.id,
            'area': asig.area if hasattr(asig, 'area') else '',
            'nombre': asig.nombre,
            'nota': nota,
            'desempeno': desempeno,
            'observaciones_pasadas': []
        })
    return jsonify(resultado)

def calcular_datos_boletin(boletin):
    """
    Función centralizada para calcular las notas, promedios y observaciones de un boletín.
    Esta función se llamará justo antes de visualizar o descargar un boletín.
    """    
    matricula = boletin.matricula
    curso_id = matricula.id_curso
    periodo_id = boletin.id_periodo
    anio_lectivo = matricula.año_lectivo

    periodo = Periodo.query.get(periodo_id)
    anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, periodo_id=periodo_id).first()
    if not anio_periodo:
        return {} # No se puede calcular si el período no está configurado para el año

    try:
        fecha_inicio = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_fin}", "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"Las fechas del período '{periodo.nombre if periodo else 'ID:'+str(periodo_id)}' no están configuradas correctamente.")

    asignaturas = Asignatura.query.join(Asignacion).filter(
        Asignacion.id_curso == matricula.id_curso,
        Asignacion.estado == 'activo',
        Asignacion.anio_lectivo == anio_lectivo
    ).options(db.joinedload(Asignatura.asignaciones)).all()

    periods = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == anio_lectivo).order_by(AnioPeriodo.fecha_inicio).all()
    current_period_index = next((i for i, p in enumerate(periods) if p.id == periodo_id), 0)

    grades_data = {}
    for asig in asignaturas:
        grades_data[str(asig.id)] = {}

       # Calcular promedio por cada período hasta el actual
        for i in range(current_period_index + 1):
            p = periods[i]
            anio_p = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, periodo_id=p.id).first()
            if not anio_p or not anio_p.fecha_inicio or not anio_p.fecha_fin:
                continue
            
            fecha_inicio_p = datetime.strptime(f"{anio_lectivo}-{anio_p.fecha_inicio}", "%Y-%m-%d").date()
            fecha_fin_p = datetime.strptime(f"{anio_lectivo}-{anio_p.fecha_fin}", "%Y-%m-%d").date()

            cal_avg = db.session.query(func.avg(Calificacion.nota))\
                .join(Asignacion, Calificacion.id_asignacion == Asignacion.id)\
                .filter(
                    Asignacion.id_asignatura == asig.id,
                    Calificacion.id_matricula == matricula.id,
                    Asignacion.anio_lectivo == anio_lectivo,
                    Calificacion.fecha_calificacion.between(fecha_inicio_p, fecha_fin_p)
                ).scalar()
            
            grades_data[str(asig.id)][f'p{i+1}'] = round(cal_avg, 2) if cal_avg is not None else 0.0

       # Obtener la observación más reciente del período actual
        latest_observation_record = db.session.query(Calificacion.observacion)\
            .join(Asignacion).filter(
                Asignacion.id_asignatura == asig.id,
                Calificacion.id_matricula == matricula.id,
                Asignacion.anio_lectivo == anio_lectivo,
                Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin),
                Calificacion.observacion.isnot(None),
                Calificacion.observacion != ''
            ).order_by(Calificacion.fecha_calificacion.desc()).first()

        grades_data[str(asig.id)]['observacion'] = latest_observation_record[0] if latest_observation_record else ''        
        
        # Calcular desempeño basado en la nota del período actual
        nota_periodo_actual = grades_data[str(asig.id)].get(f'p{current_period_index + 1}', 0.0)
        grades_data[str(asig.id)]['desempeno'] = get_desempeno(nota_periodo_actual)
        grades_data[str(asig.id)]['nota'] = nota_periodo_actual

    # Actualizar el campo grades_data del boletín en la base de datos
    boletin.grades_data = json.dumps(grades_data)
    db.session.commit()

    return grades_data

@boletines_bp.route('/')
def listar_boletines():
    
    # Obtener año lectivo activo
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']
    
    # Obtener filtros y página
    page = request.args.get('page', 1, type=int)
    curso_id = request.args.get('curso', type=int)
    periodo_id_req = request.args.get('periodo', type=int)
    busqueda = request.args.get('busqueda', '').strip()

    # Determinar el período a utilizar para el filtro.
    # Si no se pasa un período en la URL (o viene vacío), se usa el período activo por defecto.
    periodo_a_filtrar = periodo_id_req
    if periodo_a_filtrar is None:
        periodo_a_filtrar = active_config.get('periodo_id')    # Listas para los selects
    if current_user.rol == 'admin':
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []
    else: # Para docente
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().order_by(Curso.nombre).all()

    periodos = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == anio_lectivo).all()

    # Si no hay un período para filtrar, no se puede continuar.
    if not periodo_a_filtrar:
        flash('No hay un período activo o seleccionado. Por favor, configure uno.', 'warning')
        return render_template('views/informes/boletines.html',
                               boletines=[], pagination=None, cursos=cursos, periodos=periodos,
                               curso_seleccionado=curso_id, periodo_seleccionado=None,
                               periodo_activo_id=active_config.get('periodo_id'), busqueda=busqueda,
                               anio_lectivo=anio_lectivo)

    # Si no se ha seleccionado un curso, no mostrar nada.
    if not curso_id:
        return render_template('views/informes/boletines.html',
                               boletines=[], pagination=None, cursos=cursos, periodos=periodos,
                               curso_seleccionado=None, periodo_seleccionado=periodo_a_filtrar,
                               periodo_activo_id=active_config.get('periodo_id'), busqueda=busqueda,
                               anio_lectivo=anio_lectivo)


    # --- Lógica de Creación y Listado Automático (como en Libro Final) ---
    # 1. Obtener todas las matrículas activas que coincidan con los filtros
    matriculas_query = Matricula.query.filter(
        Matricula.estado == 'activo',
        Matricula.año_lectivo == anio_lectivo
    )
    if curso_id:
        matriculas_query = matriculas_query.filter(Matricula.id_curso == curso_id)

    if busqueda:
        search_term = f"%{busqueda}%"
        matriculas_query = matriculas_query.filter(
            or_(
                Matricula.nombres.ilike(search_term),
                Matricula.apellidos.ilike(search_term),
                Matricula.documento.ilike(search_term)
            )
        )
    
    pagination = matriculas_query.order_by(Matricula.apellidos, Matricula.nombres).paginate(page=page, per_page=10, error_out=False)
    matriculas_paginadas = pagination.items

    boletines = []
    for matricula in matriculas_paginadas:
        boletin = Boletin.query.filter_by(
            id_matricula=matricula.id,
            id_periodo=periodo_a_filtrar,
            anio_lectivo=anio_lectivo,
            eliminado=False
        ).first()

        if not boletin:
            boletin = Boletin(
                id_matricula=matricula.id, id_curso=matricula.id_curso,
                id_periodo=periodo_a_filtrar, anio_lectivo=anio_lectivo,
                generated_by_user_id=current_user.id
            )
            db.session.add(boletin)
            db.session.commit() # Guardar para obtener un ID
        
        boletines.append(boletin)

    # Recalcular los datos de los boletines de la página actual para mostrar promedios actualizados
    for boletin in boletines:
        calcular_datos_boletin(boletin)


    return render_template('views/informes/boletines.html',
        boletines=boletines,
        pagination=pagination,
        cursos=cursos,
        periodos=periodos,
        curso_seleccionado=curso_id,
        periodo_seleccionado=periodo_a_filtrar,
        periodo_activo_id=active_config.get('periodo_id'),
        busqueda=busqueda,
        anio_lectivo=anio_lectivo
    )

@boletines_bp.route('/generate', methods=['GET', 'POST'])
@roles_required('admin', 'docente')
def generate_boletin():
    # Obtener año lectivo activo
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']
    
    cursos = Curso.query.filter_by(estado='activo').all()
    periodos = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == anio_lectivo).all()
    

    if request.method == 'POST':
        curso_id = request.form.get('curso_id', type=int)
        periodo_id = active_config.get('periodo_id') # Usar siempre el periodo activo
        obs_generales = request.form.get('obs_generales', '')

        if not curso_id:
            flash('Debe seleccionar un curso.', 'danger')
            return redirect(url_for('boletines.listar_boletines'))

        if not periodo_id:
            flash('No hay un período activo configurado. Por favor, vaya a la configuración y active uno.', 'danger')
            return redirect(url_for('configuracion.index'))

        periodo = Periodo.query.get(periodo_id)
        if not periodo:
            flash('El período seleccionado no es válido.', 'danger')
            return redirect(url_for('boletines.listar_boletines'))

        anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, periodo_id=periodo_id).first()
        if not anio_periodo:
            flash(f"El período '{periodo.nombre}' no está configurado para el año lectivo {anio_lectivo}.", 'danger')
            return redirect(url_for('boletines.listar_boletines'))

        try:
            fecha_inicio = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_fin}", "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash(f"Las fechas del período '{periodo.nombre}' no están configuradas correctamente.", 'danger')
            return redirect(url_for('boletines.listar_boletines'))


        matriculas = Matricula.query.filter_by(id_curso=curso_id, estado='activo', año_lectivo=anio_lectivo).all()
        if not matriculas:
            flash('No hay estudiantes activos en el curso seleccionado.', 'danger')
            return redirect(url_for('boletines.listar_boletines'))

        asignaturas = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).all()

        # Obtener todos los períodos ordenados por fecha de inicio
        periods = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == anio_lectivo).order_by(AnioPeriodo.fecha_inicio).all()
        current_period_index = next((i for i, p in enumerate(periods) if p.id == periodo_id), 0)

        boletines_creados = 0
        boletines_omitidos = 0
        nombres_omitidos = []

        for matricula in matriculas:
            existing_boletin = Boletin.query.filter_by(id_matricula=matricula.id, id_periodo=periodo_id, anio_lectivo=anio_lectivo).first()
            if existing_boletin:
                boletines_omitidos += 1
                nombres_omitidos.append(f"{matricula.nombres} {matricula.apellidos}")
                continue

            grades_data = {}
            for asig in asignaturas:
                grades_data[str(asig.id)] = {}

                # Obtener asignacion para la asignatura
                asignacion = Asignacion.query.filter_by(
                    id_curso=curso_id,
                    id_asignatura=asig.id,
                    estado='activo',
                    anio_lectivo=anio_lectivo
                ).first()

                # Contar inasistencias por asignatura
                inasistencias_asig = 0
                if asignacion:
                    inasistencias_asig = db.session.query(func.count(Asistencia.id)).filter(
                        Asistencia.id_asignacion == asignacion.id,
                        Asistencia.id_matricula == matricula.id,
                        Asistencia.fecha.between(fecha_inicio, fecha_fin),
                        Asistencia.estado == 'ausente'
                    ).scalar() or 0

                # Calcular promedio por período
                for i in range(current_period_index + 1):
                    p = periods[i]
                    anio_periodo_p = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, periodo_id=p.id).first()
                    if not anio_periodo_p:
                        continue
                    fecha_inicio_p = datetime.strptime(f"{anio_lectivo}-{anio_periodo_p.fecha_inicio}", "%Y-%m-%d").date()
                    fecha_fin_p = datetime.strptime(f"{anio_lectivo}-{anio_periodo_p.fecha_fin}", "%Y-%m-%d").date()

                    cal_avg = db.session.query(
                        func.avg(Calificacion.nota)
                    ).select_from(Asignacion).join(Calificacion, Asignacion.id == Calificacion.id_asignacion).filter(
                        Asignacion.id_asignatura == asig.id,
                        Calificacion.id_matricula == matricula.id,
                        Asignacion.anio_lectivo == anio_lectivo,
                        Calificacion.fecha_calificacion.between(fecha_inicio_p, fecha_fin_p)
                    ).scalar()

                    grades_data[str(asig.id)][f'p{i+1}'] = round(cal_avg, 2) if cal_avg is not None else 0

                # Calcular PF si es período 4
                if current_period_index + 1 == 4:
                    p_values = [grades_data[str(asig.id)].get(f'p{j+1}', 0) for j in range(4)]
                    pf = sum(p_values) / len(p_values) if p_values else 0
                    grades_data[str(asig.id)]['pf'] = round(pf, 2)

                # Valores fijos
                grades_data[str(asig.id)]['fl'] = inasistencias_asig

                horas_impartidas = asignacion.horas_impartidas if asignacion and asignacion.horas_impartidas else 0
                grades_data[str(asig.id)]['ih'] = horas_impartidas

                # Observación más reciente
                latest_observation_record = db.session.query(Calificacion.observacion).join(Asignacion).filter(
                    Asignacion.id_asignatura == asig.id,
                    Calificacion.id_matricula == matricula.id,
                    Asignacion.anio_lectivo == anio_lectivo,
                    Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin),
                    Calificacion.observacion.isnot(None),
                    Calificacion.observacion != ''
                ).order_by(Calificacion.fecha_calificacion.desc()).first()

                observacion = latest_observation_record[0] if latest_observation_record else ''
                grades_data[str(asig.id)]['observacion'] = observacion

            # Calcular promedios por período para el estudiante
            period_averages = {}
            for i in range(current_period_index + 1):
                period_key = f'p{i+1}'
                notes = [grades_data[str(asig.id)].get(period_key, 0) for asig in asignaturas]
                period_averages[period_key] = round(sum(notes) / len(notes), 2) if asignaturas else 0

            if current_period_index + 1 == 4:
                p_values = [period_averages.get(f'p{j+1}', 0) for j in range(4)]
                period_averages['pf'] = round(sum(p_values) / len(p_values), 2) if p_values else 0

            period_avg = period_averages.get(f'p{current_period_index + 1}', 0)
            desempeno_periodo = get_desempeno(period_avg)

            # Establecer desempeño individual para cada asignatura
            for asig in asignaturas:
                subject_grade = grades_data[str(asig.id)].get(f'p{current_period_index + 1}', 0)
                grades_data[str(asig.id)]['desempeno'] = get_desempeno(subject_grade)
                grades_data[str(asig.id)]['nota'] = subject_grade  # Nota individual de la asignatura



            new_boletin = Boletin(
                id_matricula=matricula.id,
                id_curso=curso_id,
                id_periodo=periodo_id,
                anio_lectivo=anio_lectivo,
                grades_data=json.dumps(grades_data),
                comments=obs_generales,
                generated_by_user_id=current_user.id
            )
            db.session.add(new_boletin)
            boletines_creados += 1
        
        db.session.commit()

        if boletines_creados > 0 and boletines_omitidos > 0:
            nombres_str = ", ".join(nombres_omitidos)
            flash(f'{boletines_creados} boletines fueron generados para el período {periodo.nombre}.', 'success')
            flash(f'Se omitieron {boletines_omitidos} que ya existían para los estudiantes: {nombres_str}.', 'warning')
        elif boletines_creados > 0 and boletines_omitidos == 0:
            flash(f'{boletines_creados} boletines fueron generados para el período {periodo.nombre}.', 'success')
        elif boletines_creados == 0 and boletines_omitidos > 0:
            flash(f'No se generaron boletines nuevos. Todos para este curso y período ya existían.', 'info')
        else:
            flash('No se generó ningún boletín. Verifique que el curso tenga estudiantes matriculados.', 'info')

        return redirect(url_for('boletines.listar_boletines', curso=curso_id, periodo=periodo_id))

    return render_template('views/informes/boletines.html',
                           cursos=cursos,
                           periodos=periodos,
                           periodo_activo_id=active_config.get('periodo_id'),
                           anio_lectivo=anio_lectivo)

@boletines_bp.route('/<int:boletin_id>')
@roles_required('admin', 'docente')
def view_boletin(boletin_id):
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Handle non-AJAX request separately if needed, or just return an error
        boletin = Boletin.query.get_or_404(boletin_id)
        grades_data = json.loads(boletin.grades_data) if boletin.grades_data else {}
        return render_template('views/informes/view_boletin.html', boletin=boletin, grades=grades_data)

    try:
        boletin = Boletin.query.get_or_404(boletin_id)
        # ¡CORRECCIÓN! Se llama a la función para recalcular los datos justo antes de la visualización.
        grades_data = calcular_datos_boletin(boletin)
        
        asignaturas = Asignatura.query.filter_by(estado='activo').all()
        asignaturas_map = {str(a.id): a.nombre for a in asignaturas}

        # Determinar el número de períodos
        periods = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == boletin.anio_lectivo).order_by(AnioPeriodo.fecha_inicio).all()
        current_period_index = next((i for i, p in enumerate(periods) if p.id == boletin.id_periodo), 0)
        period_count = current_period_index + 1

        # Obtener fechas del período
        anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=boletin.anio_lectivo, periodo_id=boletin.id_periodo).first()
        fecha_inicio = None
        fecha_fin = None # Inicializar fecha_fin
        if anio_periodo and anio_periodo.fecha_inicio and anio_periodo.fecha_fin:
            fecha_inicio = datetime.strptime(f"{boletin.anio_lectivo}-{anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(f"{boletin.anio_lectivo}-{anio_periodo.fecha_fin}", "%Y-%m-%d").date()
            
        grades = []
        for asig_id, data in grades_data.items():
            # Obtener asignacion para la asignatura
            asignacion = Asignacion.query.filter_by(
                id_curso=boletin.id_curso,
                id_asignatura=int(asig_id),
                estado='activo',
                anio_lectivo=boletin.anio_lectivo
            ).first()

            # Contar inasistencias por asignatura
            inasistencias_asig = 0
            if asignacion and fecha_inicio and fecha_fin:
                inasistencias_asig = db.session.query(func.count(Asistencia.id)).filter(
                    Asistencia.id_asignacion == asignacion.id,
                    Asistencia.id_matricula == boletin.matricula.id,
                    Asistencia.fecha.between(fecha_inicio, fecha_fin),
                    Asistencia.estado == 'ausente'
                ).scalar() or 0

            grades.append({
                'asignatura': asignaturas_map.get(str(asig_id), 'Asignatura desconocida'),
                'nota': data.get('nota', ''),
                'desempeno': data.get('desempeno', ''),
                'observacion': data.get('observacion', ''),
                'ih': data.get('ih', 0),
                'fl': inasistencias_asig
            })

        boletin_data = {
            'estudiante': boletin.estudiante_nombre,
            'curso': boletin.curso_nombre,
            'anio_lectivo': boletin.anio_lectivo,
            'fecha_generacion': boletin.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
            'generado_por': boletin.creado_por,
            'observaciones_generales': boletin.comments,
            'grades': grades
        }
        current_app.logger.debug(f"boletin.grades_data: {boletin.grades_data}")
        current_app.logger.debug(f"grades: {grades}")
        return jsonify(boletin_data)
    except Exception as e:
        current_app.logger.error(f"Error en la ruta /boletines/<id>: {str(e)}", exc_info=True)
        # Return a JSON response with a 500 status code
        return jsonify({'error': 'Ocurrió un error interno al cargar los detalles del boletín.'}), 500


@boletines_bp.route('/descargar_pdf/<int:boletin_id>')
@roles_required('admin', 'docente')
def descargar_boletin_pdf(boletin_id):
    boletin = Boletin.query.get_or_404(boletin_id)
    # Se calculan los datos justo antes de generar el PDF para asegurar que estén actualizados.
    calcular_datos_boletin(boletin)

    primer_apellido = boletin.matricula.apellidos.split()[0] if boletin.matricula.apellidos else ''
    primer_nombre = boletin.matricula.nombres.split()[0] if boletin.matricula.nombres else ''
    periodo_nombre = boletin.periodo.nombre if boletin.periodo else 'SIN_PERIODO'
    filename = f"boletin_{periodo_nombre}_{primer_apellido}_{primer_nombre}.pdf"
    buffer = generar_boletin_pdf(boletin_id)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@boletines_bp.route('/enviar_boletin/<int:boletin_id>', methods=['POST'])
@roles_required('admin', 'docente')
def enviar_boletin(boletin_id):
    try:
        boletin = Boletin.query.get_or_404(boletin_id)
        matricula = boletin.matricula

        if not matricula or not matricula.email:
            return jsonify({'success': False, 'message': 'El estudiante no tiene una dirección de correo electrónico registrada.'})

        # Se calculan los datos justo antes de enviar para asegurar que estén actualizados.
        calcular_datos_boletin(boletin)

        # 1. Generate PDF
        buffer = generar_boletin_pdf(boletin_id)
        pdf_data = buffer.getvalue()
        buffer.close()

        # 3. Email Body
        # Cuerpo del correo con diseño mejorado, similar al de pagos
        body = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
                .header {{ background-color: #2C3E50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .footer {{ background-color: #f2f2f2; color: #666; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Jardín Infantil Sonrisas</h1>
                    <p>Aprendiendo y Sonriendo</p>
                </div>
                <div class="content">
                    <h3>Boletín Académico</h3>
                    <p>Estimado/a acudiente de <strong>{matricula.nombres} {matricula.apellidos}</strong>,</p>
                    <p>
                        Nos complace compartir con usted el boletín de calificaciones del <strong>{boletin.periodo.nombre if boletin.periodo else ''}</strong> 
                        periodo para el año lectivo <strong>{boletin.anio_lectivo}</strong>.
                    </p>
                    <p>
                        El documento se encuentra adjunto a este correo en formato PDF. Le invitamos a revisarlo para estar al tanto del progreso académico del estudiante.
                    </p>
                    
                    <br>
                    <p>Atentamente,</p>
                    <p><strong>Equipo Académico - Jardín Infantil Sonrisas</strong></p>

                    <p class="note">
                    Si tiene alguna pregunta sobre este Boletin, no dude en contactarnos.<br>
                    Teléfono: 300 149 8933 | Email: jardininfantilsonrisas2023@gmail.com
                </p>
                </div>
                <div class="footer">
                <p>© {datetime.now().year} Jardín Infantil Sonrisas. Todos los derechos reservados.</p>
                    <p>Este es un mensaje automático, por favor no responda a este correo.
                </p>
            </div>
            </div>
        </body>
        </html>
        """
        try:
            # Configurar email con Flask-Mail
            msg = Message(
                subject=f"Boletín Académico - {boletin.anio_lectivo} - Jardín Infantil Sonrisas",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[matricula.email],
                html=body
            )

            # Adjuntar PDF
            primer_apellido = boletin.matricula.apellidos.split()[0] if boletin.matricula.apellidos else ''
            primer_nombre = boletin.matricula.nombres.split()[0] if boletin.matricula.nombres else ''
            periodo_nombre = boletin.periodo.nombre if boletin.periodo else 'SIN_PERIODO'
            filename = f"boletin_{periodo_nombre}_{primer_apellido}_{primer_nombre}.pdf"
            msg.attach(
                filename=filename,
                content_type='application/pdf',
                data=pdf_data
            )
            mail.send(msg)
            return jsonify({'success': True, 'message': f'Boletín enviado exitosamente a {matricula.email}'})
        except Exception as e:
            current_app.logger.error(f"Error al enviar correo desde boletines: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error al enviar correo: {str(e)}'})
    
    except Exception as e:
        current_app.logger.error(f"Error en la ruta /enviar_boletin: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Ocurrió un error interno al intentar enviar el boletín.'})

@boletines_bp.route('/info_contacto_boletin/<int:boletin_id>')
@roles_required('admin', 'docente')
def info_contacto_boletin(boletin_id):
    boletin = Boletin.query.get_or_404(boletin_id)
    matricula = boletin.matricula
    if not matricula:
        return jsonify({'error': 'Matrícula no encontrada'}), 404
    
    return jsonify({
        'nombre': f"{matricula.nombres} {matricula.apellidos}",
        'whatsapp': matricula.telefono
    })


@boletines_bp.route('/delete/<int:boletin_id>', methods=['POST'])
@roles_required('admin')
def delete_boletin(boletin_id):
    boletin = Boletin.query.get_or_404(boletin_id)
    try:
        boletin.eliminado = True
        boletin.eliminado_por = current_user.id
        boletin.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Boletín enviado a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al enviar boletín {boletin_id} a la papelera: {e}")
        flash('Error al enviar boletín a la papelera.', 'danger')
    
    return redirect(url_for('boletines.listar_boletines'))

@boletines_bp.route('/descargar_todos_zip')
@roles_required('admin', 'docente')
def descargar_todos_zip():
    curso_id = request.args.get('curso', type=int)
    periodo_id_req = request.args.get('periodo', type=int)
    active_config = get_active_config()
    anio_lectivo = active_config.get('anio')

    periodo_id = periodo_id_req
    if periodo_id is None:
        periodo_id = active_config.get('periodo_id')

    if not all([curso_id, periodo_id, anio_lectivo]):
        flash('Faltan parámetros (curso, período o año lectivo) para la descarga masiva.', 'danger')
        return redirect(url_for('boletines.listar_boletines'))
    
    # --- INICIO DE LA OPTIMIZACIÓN ---

    # 1. Obtener todas las matrículas activas del curso de una vez.
    matriculas_activas = Matricula.query.filter_by(
        id_curso=curso_id,
        año_lectivo=anio_lectivo,
        estado='activo'
    ).all()

    if not matriculas_activas:
        flash('No hay estudiantes activos en este curso para generar boletines.', 'warning')
        return redirect(url_for('boletines.listar_boletines', curso=curso_id, periodo=periodo_id))

    matriculas_ids = [m.id for m in matriculas_activas]

    # 2. Obtener todos los boletines existentes para estas matrículas en una sola consulta.
    boletines_existentes_query = Boletin.query.filter(
        Boletin.id_matricula.in_(matriculas_ids),
        Boletin.id_periodo == periodo_id,
        Boletin.anio_lectivo == anio_lectivo
    )
    boletines_existentes = {b.id_matricula: b for b in boletines_existentes_query.all()}

    # 3. Identificar qué boletines necesitan ser creados.
    boletines_a_crear = []
    for matricula in matriculas_activas:
        if matricula.id not in boletines_existentes:
            boletin_nuevo = Boletin(
                id_matricula=matricula.id,
                id_curso=matricula.id_curso,
                id_periodo=periodo_id,
                anio_lectivo=anio_lectivo,
                generated_by_user_id=current_user.id
            )
            boletines_a_crear.append(boletin_nuevo)

    # 4. Crear los boletines faltantes en una sola transacción (bulk insert).
    if boletines_a_crear:
        db.session.bulk_save_objects(boletines_a_crear)
        db.session.commit()
        # Volver a consultar para tener los IDs de los nuevos boletines
        boletines_existentes = {b.id_matricula: b for b in boletines_existentes_query.all()}

    # 5. Obtener todos los boletines (existentes y recién creados) que se van a procesar.
    boletines_a_generar = []
    for matricula in matriculas_activas:
        if matricula.id in boletines_existentes:
            boletines_a_generar.append(boletines_existentes[matricula.id])

    if not boletines_a_generar:
        flash('No hay boletines para descargar con los filtros seleccionados.', 'warning')
        return redirect(url_for('boletines.listar_boletines', curso=curso_id, periodo=periodo_id))

    # 6. Recalcular los datos de todos los boletines en una sola pasada.
    # Esto es crucial para evitar el problema N+1 de la función `calcular_datos_boletin`.
    # Aunque la función original hace muchas queries, la llamaremos aquí para mantener la lógica de cálculo,
    # pero idealmente esta función también debería ser optimizada para trabajar en lotes.
    # Por ahora, el mayor cuello de botella (commit en bucle) ya se ha solucionado.
    boletines_para_actualizar_datos = []
    for boletin in boletines_a_generar:
        calcular_datos_boletin(boletin)
        boletines_para_actualizar_datos.append(boletin)

    # 7. Actualizar los `grades_data` en la base de datos en una sola transacción.
    if boletines_para_actualizar_datos:
        # Usamos merge para actualizar los objetos que ya existen en la sesión.
        for b in boletines_para_actualizar_datos:
            db.session.merge(b)
        db.session.commit()

    # --- FIN DE LA OPTIMIZACIÓN ---

    # Crear un archivo ZIP en memoria
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for boletin in boletines_a_generar:
            try:
                # Generar el PDF para cada boletín
                pdf_buffer = generar_boletin_pdf(boletin.id)
                
                # Crear un nombre de archivo único para cada PDF
                primer_apellido = boletin.matricula.apellidos.split()[0] if boletin.matricula.apellidos else ''
                primer_nombre = boletin.matricula.nombres.split()[0] if boletin.matricula.nombres else ''
                pdf_filename = f"Boletin_{primer_apellido}_{primer_nombre}.pdf"
                
                # Añadir el PDF al archivo ZIP
                zf.writestr(pdf_filename, pdf_buffer.getvalue())
            except Exception as e:
                current_app.logger.error(f"Error generando PDF para boletín {boletin.id}: {e}")
                # Opcional: podrías añadir un archivo de texto al ZIP indicando el error.
                error_filename = f"ERROR_boletin_{boletin.matricula.apellidos}_{boletin.matricula.nombres}.txt"
                error_message = f"No se pudo generar el boletín para el estudiante {boletin.matricula.nombres} {boletin.matricula.apellidos}.\nError: {str(e)}"
                zf.writestr(error_filename, error_message)
                continue # Continuar con el siguiente boletín

    zip_buffer.seek(0)
    curso = Curso.query.get(curso_id)
    zip_filename = f"Boletines_{curso.nombre.replace(' ', '_')}_{anio_lectivo}.zip"

    return make_response(zip_buffer.read()), 200, {'Content-Type': 'application/zip', 'Content-Disposition': f'attachment; filename={zip_filename}'}



def generar_boletin_pdf(boletin_id):
    boletin = Boletin.query.get_or_404(boletin_id)
    buffer = BytesIO()
    
    # Documento con márgenes ajustados
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=20, leftMargin=20,
        topMargin=30, bottomMargin=30
    )

    # --- ESTILOS ---
    styles = getSampleStyleSheet()
    estilo_base = ParagraphStyle(
        'Base', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=10, spaceAfter=1
    )
    estilo_negrita = ParagraphStyle('Negrita', parent=estilo_base, fontName='Helvetica-Bold', fontSize=8)
    estilo_centrado = ParagraphStyle('Centrado', parent=estilo_base, alignment=TA_CENTER)
    estilo_titulo_centro = ParagraphStyle('TituloCentro', parent=estilo_negrita, fontSize=10, alignment=TA_CENTER, spaceAfter=2)
    estilo_small_gray = ParagraphStyle('SmallGray', parent=estilo_base, textColor=HexColor("#666666"), fontSize=7)
    estilo_centrado_small_gray = ParagraphStyle('CentradoSmallGray', parent=estilo_base, alignment=TA_CENTER, textColor=HexColor("#666666"), fontSize=7)
    estilo_centrado_negrita = ParagraphStyle('CentradoNegrita', parent=estilo_negrita, alignment=TA_CENTER)
    estilo_normal = ParagraphStyle('Normal', parent=estilo_base, fontName='Helvetica', fontSize=8)
    estilo_header_cell = ParagraphStyle('HeaderCell', parent=estilo_negrita, fontSize=7, alignment=TA_CENTER)

    # Config académica
    config = ConfiguracionLibro.obtener_configuracion_actual()
    nota_basico = config.nota_basico if config else 3.0

    # Marca de agua
    def add_background(canvas, doc_):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        marca_agua_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
        if os.path.exists(marca_agua_path):
            canvas.saveState()
            canvas.setFillAlpha(0.10)
            page_width, page_height = letter
            logo_width, logo_height = 400, 400
            x_center = (page_width - logo_width) / 2
            y_center = (page_height - logo_height) / 2
            canvas.drawImage(marca_agua_path, x_center, y_center, width=logo_width, height=logo_height, mask='auto')
            canvas.restoreState()

    # --- CREACIÓN DE TABLAS INDIVIDUALES (las seguiremos anidando) ---
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    logo_left_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
    logo_right_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logo-colombia.png')

    logo_left = Image(logo_left_path, width=0.8*inch, height=0.8*inch) if os.path.exists(logo_left_path) else ""
    logo_right = Image(logo_right_path, width=0.8*inch, height=0.8*inch) if os.path.exists(logo_right_path) else ""

    # CENTER INFO (header central)
    center_info = Table([
        [Paragraph("REPUBLICA DE COLOMBIA", estilo_titulo_centro)],
        [Paragraph("<b>JARDÍN INFANTIL SONRISAS</b>", estilo_titulo_centro)],
        [Paragraph("VALLEDUPAR (CESAR)", estilo_centrado)],
        [Paragraph("26723 DEL 18 DE DICIEMBRE DE 2023", estilo_centrado)],
        [Paragraph("DANE: 28532400019 NIT: 800045481-3", estilo_centrado)]
    ], colWidths=[5.5*inch])
    center_info.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1)
    ]))

    # Header (sin borde)
    header_table = Table([[logo_left, center_info, logo_right]],
                         colWidths=[1.0*inch, 5.5*inch, 1.0*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # Info estudiante (con borde)
    info_estudiante = Table([[
        Paragraph(f"{boletin.matricula.apellidos} {boletin.matricula.nombres}", estilo_centrado_negrita),
        Paragraph(f"JIS-{boletin.matricula.documento}", estilo_centrado_negrita),
        Paragraph(boletin.curso.nombre if boletin.curso else '', estilo_centrado_negrita)
    ]], colWidths=[3.5*inch, 2.5*inch, 1.5*inch])
    info_estudiante.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('INNERGRID', (0,0), (-1,-1), 1, black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # Periodo (con borde)
    periodo_table = Table([[
        Paragraph("PRINCIPAL", estilo_centrado_negrita),
        Paragraph(f"PERÍODO {boletin.periodo.nombre if boletin.periodo else 'PRIMERO'}", estilo_centrado_negrita),
        Paragraph(str(boletin.anio_lectivo), estilo_centrado_negrita)
    ]], colWidths=[3.5*inch, 2.5*inch, 1.5*inch])
    periodo_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('INNERGRID', (0,0), (-1,-1), 1, black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # Fecha impresion
    fecha_impresion = Table([[Paragraph(f"FECHA IMPRESIÓN: {datetime.now().strftime('%Y-%m-%d')}", estilo_centrado_small_gray)]],
                             colWidths=[7.5*inch])
    fecha_impresion.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))

    # --- CALIFICACIONES ---
    grades = {}
    if boletin.grades_data:
        try:
            grades = json.loads(boletin.grades_data)
        except Exception:
            grades = {}

    asignaturas = Asignatura.query.all()
    asignaturas_map = {str(a.id): a for a in asignaturas}

    # Determinar el número de períodos
    periods = Periodo.query.join(AnioPeriodo).filter(AnioPeriodo.anio_lectivo == boletin.anio_lectivo).order_by(AnioPeriodo.fecha_inicio).all()
    current_period_index = next((i for i, p in enumerate(periods) if p.id == boletin.id_periodo), 0)
    period_count = current_period_index + 1

    # --- PUESTO Y PROMEDIO ---
    # Obtener fechas del período
    anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=boletin.anio_lectivo, periodo_id=boletin.id_periodo).first()
    if anio_periodo:
        fecha_inicio = datetime.strptime(f"{boletin.anio_lectivo}-{anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(f"{boletin.anio_lectivo}-{anio_periodo.fecha_fin}", "%Y-%m-%d").date()
    else:
        fecha_inicio = None
        fecha_fin = None

    items = []
    for asig_id, d in grades.items():
        asig_obj = asignaturas_map.get(str(asig_id))
        if not asig_obj:
            continue
        asignatura = asig_obj.nombre

        # Obtener asignacion para la asignatura
        asignacion = Asignacion.query.filter_by(
            id_curso=boletin.id_curso,
            id_asignatura=asig_obj.id,
            estado='activo',
            anio_lectivo=boletin.anio_lectivo
        ).first()

        # Contar inasistencias por asignatura
        inasistencias_asig = 0
        if asignacion and fecha_inicio and fecha_fin:
            inasistencias_asig = db.session.query(func.count(Asistencia.id)).filter(
                Asistencia.id_asignacion == asignacion.id,
                Asistencia.id_matricula == boletin.matricula.id,
                Asistencia.fecha.between(fecha_inicio, fecha_fin),
                Asistencia.estado == 'ausente'
            ).scalar() or 0

        item = {
            "asignatura": asignatura,
            "porcentaje": "[100%]",
            **d
        }
        item['fl'] = inasistencias_asig
        items.append(item)

    # Construir columnas dinámicamente
    columns = ['ASIGNATURA', 'DESEMPEÑO'] + [f'P{i+1}' for i in range(period_count)]
    if period_count == 4:
        columns.append('PF')
    columns += ['FL', 'IH'] 

    tabla_data = [[Paragraph(f"<b>{col}</b>", estilo_header_cell) for col in columns]]

    for item in items:
        row = [
            Paragraph(f"{item['asignatura']} {item['porcentaje']}", estilo_base),
            Paragraph(item['desempeno'], estilo_base),
        ]
        for i in range(period_count):
            note = item.get(f'p{i+1}')
            row.append(Paragraph("" if note is None else f"{note:.1f}", estilo_centrado))
        if period_count == 4:
            pf = item.get('pf')
            row.append(Paragraph("" if pf is None else f"{pf:.1f}", estilo_centrado))
        row.append(Paragraph(str(item.get('fl', 0)), estilo_centrado))
        row.append(Paragraph(str(item.get('ih', 1)), estilo_centrado))
        tabla_data.append(row)
        if item.get('observacion'):
            obs_row = [Paragraph(item['observacion'], estilo_small_gray)] + [""] * (len(columns) - 1)
            tabla_data.append(obs_row)

    fixed_width = 3.0*inch + 1.5*inch  # asignatura + desempeno
    total_width = 7.5*inch
    extra_columns = len(columns) - 2
    if extra_columns > 0:
        extra_width = (total_width - fixed_width) / extra_columns
        colWidths = [3.0*inch, 1.5*inch] + [extra_width] * extra_columns
    else:
        colWidths = [3.0*inch, 1.5*inch]
    calificaciones_table = Table(tabla_data, colWidths=colWidths)
    table_style = [
        ('BOX', (0,0), (-1,-1), 1, black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('BACKGROUND', (0,0), (-1,0), HexColor("#e0e0e0")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]
    

    # Observaciones spanning
    for i, row in enumerate(tabla_data[1:], 1):
        if isinstance(row[0], Paragraph) and len(row) > 1 and row[1] == "":
            # Es fila de observación, span completo
            table_style.append(('SPAN', (0,i), (-1,i)))
            table_style.append(('BACKGROUND', (0,i), (-1,i), HexColor("#f9f9f9")))
        elif isinstance(row[0], Paragraph) and len(row[0].text) > 50:
            # Texto largo en fila normal
            table_style.append(('SPAN', (0,i), (-1,i)))
            table_style.append(('BACKGROUND', (0,i), (-1,i), HexColor("#f9f9f9")))
    calificaciones_table.setStyle(TableStyle(table_style))

    # Calculate promedio_general from grades_data
    subject_notes = [d.get(f'p{period_count}', 0) for d in grades.values()]
    promedio_general = round(sum(subject_notes) / len(subject_notes), 2) if subject_notes else 0
    desempeno_general = get_desempeno(promedio_general).upper()
    promedio_str = f"{promedio_general:.2f}"

    # For ranking
    boletines_curso = Boletin.query.filter_by(id_curso=boletin.id_curso, id_periodo=boletin.id_periodo, anio_lectivo=boletin.anio_lectivo, eliminado=False).all()
    ranking = []
    for b in boletines_curso:
        g = json.loads(b.grades_data) if b.grades_data else {}
        subj_notes = [d.get(f'p{period_count}', 0) for d in g.values()]
        avg = round(sum(subj_notes) / len(subj_notes), 2) if subj_notes else 0
        ranking.append((b.matricula.id, avg))
    ranking.sort(key=lambda x: x[1], reverse=True)
    puesto = next((idx+1 for idx, (mid, _) in enumerate(ranking) if mid == boletin.matricula.id), 1)

    asignaturas_reprobadas = 0
    if grades:
        for data in grades.values():
            nota = data.get('nota')
            if nota is not None and nota < nota_basico:
                asignaturas_reprobadas += 1

    puesto_promedio = Table([
        [Paragraph(f"PUESTO No [ {puesto} ]   PROM [ {promedio_str} ]   DESEMPEÑO: {desempeno_general}", estilo_centrado_negrita)],
        [Paragraph(f"ASIGNATURAS REPROBADAS: {asignaturas_reprobadas}", estilo_centrado_negrita)]
    ], colWidths=[7.5*inch])
    puesto_promedio.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # --- OBSERVACIONES ---
    observaciones_table = Table([[Paragraph("OBSERVACIONES", estilo_negrita)]], colWidths=[7.5*inch])
    observaciones_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('BACKGROUND', (0,0), (-1,-1), HexColor("#f0f0f0")),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # --- PIE ---
    pie_info = Table([
        [Paragraph("*** FIN DEL REPORTE DE CALIFICACIONES PARA EL ESTUDIANTE ***", estilo_centrado)],
        [Paragraph(f"{boletin.matricula.apellidos} {boletin.matricula.nombres}", estilo_centrado),
         Paragraph(f"Documento: {boletin.matricula.documento}", estilo_centrado)]
    ], colWidths=[4.0*inch, 3.5*inch])
    pie_info.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, black),
        ('SPAN', (0,0), (-1,0)),
        ('INNERGRID', (0,1), (-1,-1), 1, black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # --- FIRMAS ---
    rector_nombre, _, rector_firma_url = obtener_datos_rector()
    firma_img = None
    if rector_firma_url:
        firma_path = os.path.join(base_dir, 'frontend', 'static', rector_firma_url.lstrip('/static/'))
        if os.path.exists(firma_path):
            firma_img = Image(firma_path, width=2.0*inch, height=0.8*inch, mask='auto')

    firmas = [
        # Primera fila: firma del rector y raya para director centradas
        [firma_img if firma_img else Paragraph("", estilo_normal),
         Paragraph("", estilo_normal)],

        # Segunda fila: nombre del rector y raya para director
        [Paragraph(rector_nombre or "RECTOR(A)", estilo_negrita),
         Paragraph("___________________", estilo_normal)],

        # Tercera fila: cargos
        [Paragraph("RECTOR(A)", estilo_negrita),
         Paragraph("DIRECTOR(A) DE GRUPO", estilo_negrita)]
    ]

    firmas_table = Table(firmas, colWidths=[2.5*inch, 2.5*inch])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),   # centrar todo en cada celda
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),  # alinear vertical
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    # Centrar la tabla de firmas en la página
    centered_firmas = Table([[firmas_table]], colWidths=[7.5*inch])
    centered_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 80),  # Desplazar más a la derecha
    ]))

    # --- MASTER TABLE: agrupa todas las tablas anteriores en UNA sola columna ---
    master_rows = [
        [header_table],
        [info_estudiante],
        [periodo_table],
        [fecha_impresion],
        [calificaciones_table],
        [puesto_promedio],
        [observaciones_table],
        [pie_info],
        [centered_firmas]
    ]
    master_table = Table(master_rows, colWidths=[7.5*inch])

    # Estilos de la tabla maestra: sin borde global, padding por fila para separarlas
    master_style = [('VALIGN', (0,0), (-1,-1), 'TOP')]
    # aplicar padding consistente entre filas
    for i in range(len(master_rows)):
        master_style.append(('LEFTPADDING', (0,i), (0,i), 0))
        master_style.append(('RIGHTPADDING', (0,i), (0,i), 0))
        master_style.append(('TOPPADDING', (0,i), (0,i), 0))
        master_style.append(('BOTTOMPADDING', (0,i), (0,i), 0))
    master_table.setStyle(TableStyle(master_style))

    # Construir Story con la tabla maestra
    Story = [master_table]

    # Renderizar el documento con la marca de agua
    doc.build(Story, onFirstPage=add_background, onLaterPages=add_background)
    buffer.seek(0)
    return buffer