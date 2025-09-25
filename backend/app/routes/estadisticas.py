from flask import Blueprint, jsonify, request, render_template, flash, redirect, url_for
from app.models import Matricula, Asistencia, Calificacion, Curso, Asignacion, AnioPeriodo
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from app.utils.decorators import admin_required
from app.utils.pdf_generador_estadisticas import generate_statistics_pdf
from app.services.configuracion_service import get_active_config
from io import BytesIO

estadisticas_bp = Blueprint('estadisticas', __name__, url_prefix='/informes/estadisticas')

@estadisticas_bp.route('/')
@admin_required
def estadisticas():
    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None

    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']
    # Obtener período activo
    active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, estado='activo').first()
    if active_anio_periodo:
        periodo_inicio = active_anio_periodo.fecha_inicio  # MM-DD
        periodo_fin = active_anio_periodo.fecha_fin
        current_year = datetime.now().year
        start_date = datetime(current_year, int(periodo_inicio[:2]), int(periodo_inicio[3:]))
        end_date = datetime(current_year, int(periodo_fin[:2]), int(periodo_fin[3:]))
        if end_date < start_date:
            end_date = end_date.replace(year=current_year + 1)
    else:
        start_date = None
        end_date = None
    # Solo cursos con matrículas activas en el año lectivo actual
    cursos_ids = db.session.query(Matricula.id_curso).filter(Matricula.año_lectivo == anio_lectivo, Matricula.estado == 'activo').distinct().all() if anio_lectivo else []
    cursos_ids = [c[0] for c in cursos_ids]
    cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').all() if cursos_ids else []
    cursos_nombres = [curso.nombre for curso in cursos]
    # Estadísticas de género SOLO del año lectivo activo
    genero_stats = db.session.query(
        Matricula.genero,
        Matricula.id_curso,
        func.count(Matricula.id).label('total')
    ).filter(Matricula.estado == 'activo')
    if anio_lectivo:
        genero_stats = genero_stats.filter(Matricula.año_lectivo == anio_lectivo)
    genero_stats = genero_stats.group_by(Matricula.genero, Matricula.id_curso).all()
    datos_genero_por_grado = {}
    total_hombres = 0
    total_mujeres = 0
    for curso in cursos:
        datos_genero_por_grado[curso.nombre] = {
            'hombres': sum([g.total for g in genero_stats if g.id_curso == curso.id and g.genero in ['masculino', 'otro']]),
            'mujeres': sum([g.total for g in genero_stats if g.id_curso == curso.id and g.genero in ['femenino', 'sin_especificar']])
        }
        total_hombres += datos_genero_por_grado[curso.nombre]['hombres']
        total_mujeres += datos_genero_por_grado[curso.nombre]['mujeres']
    # Matrículas por curso SOLO del año lectivo activo
    matriculas_por_curso = [sum([g.total for g in genero_stats if g.id_curso == curso.id]) for curso in cursos]
    # Asistencia por grado y periodo SOLO del año lectivo activo
    datos_asistencia_por_grado = {}
    for curso in cursos:
        matriculas = Matricula.query.filter_by(id_curso=curso.id, estado='activo')
        if anio_lectivo:
            matriculas = matriculas.filter(Matricula.año_lectivo == anio_lectivo)
        matriculas = matriculas.all()
        if not matriculas:
            continue
        # Semanal (últimos 5 días hábiles)
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        fechas_semana = [(datetime.now() - timedelta(days=(datetime.now().weekday() - i))).date() for i in range(5)]
        asistencia_semanal = {'labels': dias_semana, 'data': []}
        for dia, fecha in zip(dias_semana, fechas_semana):
            query = Asistencia.query.filter(
                Asistencia.id_matricula.in_([m.id for m in matriculas]),
                Asistencia.fecha == fecha,
                Asistencia.estado.in_(['asistencia', 'presente'])
            )
            if start_date and end_date:
                query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
            total_asistencias = query.count()
            # ...
            asistencia_semanal['data'].append(total_asistencias)
        # Mensual (días del mes actual)
        hoy = datetime.now().date()
        primer_dia_mes = hoy.replace(day=1)
        dias_mes = [(primer_dia_mes + timedelta(days=i)) for i in range((hoy - primer_dia_mes).days + 1)]
        asistencia_mensual = {'labels': [d.strftime('%d/%m') for d in dias_mes], 'data': []}
        for fecha in dias_mes:
            query = Asistencia.query.filter(
                Asistencia.id_matricula.in_([m.id for m in matriculas]),
                Asistencia.fecha == fecha,
                Asistencia.estado.in_(['asistencia', 'presente'])
            )
            if start_date and end_date:
                query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
            total_asistencias = query.count()
            # ...
            asistencia_mensual['data'].append(total_asistencias)
        # Diario (últimos 7 días)
        dias_diarios = [(datetime.now() - timedelta(days=i)).date() for i in range(6, -1, -1)]
        asistencia_diaria = {'labels': [d.strftime('%a %d') for d in dias_diarios], 'data': []}
        for fecha in dias_diarios:
            query = Asistencia.query.filter(
                Asistencia.id_matricula.in_([m.id for m in matriculas]),
                Asistencia.fecha == fecha,
                Asistencia.estado.in_(['asistencia', 'presente'])
            )
            if start_date and end_date:
                query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
            total_asistencias = query.count()
            # ...
            asistencia_diaria['data'].append(total_asistencias)
        datos_asistencia_por_grado[curso.nombre] = {
            'semanal': asistencia_semanal,
            'mensual': asistencia_mensual,
            'diario': asistencia_diaria
        }
    # Rendimiento académico por grado y periodo SOLO del año lectivo activo
    datos_rendimiento_por_grado_periodo = {}
    for curso in cursos:
        matriculas = Matricula.query.filter_by(id_curso=curso.id, estado='activo')
        if anio_lectivo:
            matriculas = matriculas.filter(Matricula.año_lectivo == anio_lectivo)
        matriculas = matriculas.all()
        if not matriculas:
            continue
        asignaciones = Asignacion.query.filter_by(id_curso=curso.id).all()
        semana_actual = datetime.now().isocalendar()[1]
        rendimiento_semanal = {'labels': [], 'data': []}
        for asignacion in asignaciones:
            promedio = db.session.query(
                func.avg(Calificacion.nota).label('promedio')
            ).filter(
                Calificacion.id_asignacion == asignacion.id,
                extract('week', Calificacion.fecha_calificacion) == semana_actual
            )
            if anio_lectivo:
                promedio = promedio.join(Matricula, Calificacion.id_matricula == Matricula.id).filter(
                    Matricula.año_lectivo == anio_lectivo,
                    Calificacion.fecha_calificacion >= start_date if start_date else True,
                    Calificacion.fecha_calificacion <= end_date if end_date else True
                )
            promedio = promedio.scalar() or 0
            rendimiento_semanal['labels'].append(asignacion.asignatura.nombre[:15] + '...')
            rendimiento_semanal['data'].append(round(promedio, 2))
        mes_actual = datetime.now().month
        rendimiento_mensual = {'labels': [], 'data': []}
        for asignacion in asignaciones:
            promedio = db.session.query(
                func.avg(Calificacion.nota).label('promedio')
            ).filter(
                Calificacion.id_asignacion == asignacion.id,
                extract('month', Calificacion.fecha_calificacion) == mes_actual
            )
            if anio_lectivo:
                promedio = promedio.join(Matricula, Calificacion.id_matricula == Matricula.id).filter(
                    Matricula.año_lectivo == anio_lectivo,
                    Calificacion.fecha_calificacion >= start_date if start_date else True,
                    Calificacion.fecha_calificacion <= end_date if end_date else True
                )
            promedio = promedio.scalar() or 0
            rendimiento_mensual['labels'].append(asignacion.asignatura.nombre[:15] + '...')
            rendimiento_mensual['data'].append(round(promedio, 2))
        ultimas_calificaciones = {'labels': [], 'data': []}
        for asignacion in asignaciones:
            promedio = db.session.query(
                func.avg(Calificacion.nota).label('promedio')
            ).filter(
                Calificacion.id_asignacion == asignacion.id,
                Calificacion.fecha_calificacion >= datetime.now() - timedelta(days=7)
            )
            if anio_lectivo:
                promedio = promedio.join(Matricula, Calificacion.id_matricula == Matricula.id).filter(
                    Matricula.año_lectivo == anio_lectivo,
                    Calificacion.fecha_calificacion >= start_date if start_date else True,
                    Calificacion.fecha_calificacion <= end_date if end_date else True
                )
            promedio = promedio.scalar() or 0
            ultimas_calificaciones['labels'].append(asignacion.asignatura.nombre[:15] + '...')
            ultimas_calificaciones['data'].append(round(promedio, 2))

        datos_rendimiento_por_grado_periodo[curso.nombre] = {
            'semanal': rendimiento_semanal,
            'mensual': rendimiento_mensual,
            'diario': ultimas_calificaciones
        }
    if anio_lectivo:
        # Datos diarios por curso (últimos 7 días)
        datos_diarios_por_curso = {}
        for curso in cursos:
            matriculas = Matricula.query.filter_by(id_curso=curso.id, estado='activo')
            if anio_lectivo:
                matriculas = matriculas.filter(Matricula.año_lectivo == anio_lectivo)
            matriculas = matriculas.all()
            if not matriculas:
                continue
            dias = [(datetime.now() - timedelta(days=i)).date() for i in range(6, -1, -1)]
            asistencia_diaria = {'labels': [d.strftime('%a %d') for d in dias], 'data': []}
            for dia in dias:
                query = Asistencia.query.filter(
                    Asistencia.id_matricula.in_([m.id for m in matriculas]),
                    Asistencia.fecha == dia,
                    Asistencia.estado == 'asistencia'
                )
                if start_date and end_date:
                    query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
                total_asistencias = query.count()
                asistencia_diaria['data'].append(total_asistencias)
            datos_diarios_por_curso[curso.nombre] = asistencia_diaria
    else:
        datos_diarios_por_curso = {}

    return render_template('views/informes/estadisticas.html',
        cursos_nombres=cursos_nombres,
        total_hombres=total_hombres,
        total_mujeres=total_mujeres,
        matriculas_por_curso=matriculas_por_curso,
        datos_genero_por_grado=datos_genero_por_grado,
        datos_asistencia_por_grado=datos_asistencia_por_grado,
        datos_rendimiento_por_grado_periodo=datos_rendimiento_por_grado_periodo,
        datos_diarios_por_curso=datos_diarios_por_curso,
        filtro_diario=True,
        status='success'
    )
    

@estadisticas_bp.route('/api/exportar', methods=['POST'])
@admin_required
def exportar_estadisticas():
    try:
        data = request.json
        grado = request.args.get('grado', 'todos')

        graficas = data.get('graficas', []) if data else []
        if not graficas or len(graficas) == 0:
            return jsonify({'status': 'error', 'message': 'No hay datos para exportar'}), 400

        # Generar PDF con las gráficas
        pdf_data = generate_statistics_pdf(graficas, grado)

        # Crear respuesta
       
        buffer = BytesIO()
        buffer.write(pdf_data)
        buffer.seek(0)

        return buffer.getvalue(), 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename=estadisticas_{grado}.pdf'
        }

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500