from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, flash, current_app, redirect, url_for
from flask_login import current_user
from app.utils.decorators import roles_required
from app.models import Calificacion, Asignacion, Curso, Matricula, Asignatura, AnioPeriodo, Actividad
from app.services.configuracion_service import get_active_config, get_active_period_id
from app import db

calificacion_bp = Blueprint('calificacion', __name__, url_prefix='/calificaciones')

@calificacion_bp.route('/obtener_asignaturas')
@roles_required('admin', 'docente')
def obtener_asignaturas():
    curso_id = request.args.get('curso_id', type=int)
    if not curso_id:
        return jsonify({"error": "Se requiere el ID del curso"}), 400

    try:
        active_config = get_active_config()
        if not active_config:
            return jsonify({'error': 'No hay un año lectivo configurado como activo'}), 400
        anio_lectivo = active_config['anio']
        periodo_id = get_active_period_id()
        
        # Query for active assignments for the given course and year
        asignaturas_query = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        )

        # Filter by teacher if the current user is a 'docente'
        if not current_user.is_admin():
            asignaturas_query = asignaturas_query.filter(Asignacion.id_docente == current_user.id)

        # Get unique subjects
        asignaturas = asignaturas_query.distinct().all()

        return jsonify([{
            'id': a.id,
            'nombre': a.nombre
        } for a in asignaturas])

    except Exception as e:
        current_app.logger.error(f"Error getting subjects: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno al obtener asignaturas"}), 500

@calificacion_bp.route('/', methods=['GET'])
@roles_required('admin', 'docente')
def index():
    curso_id = request.args.get('curso', type=int)
    asignatura_id = request.args.get('asignatura', type=int)
    fecha_str = request.args.get('fecha')
    busqueda = request.args.get('busqueda', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Obtener año lectivo activo
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']
    periodo_id = get_active_period_id()

    # Get available courses based on user's role and year
    cursos_query = Curso.query.join(Asignacion).filter(
        Asignacion.estado == 'activo',
        Asignacion.anio_lectivo == anio_lectivo
    )
    if not current_user.is_admin():
        cursos_query = cursos_query.filter(Asignacion.id_docente == current_user.id)
    lista_cursos = cursos_query.distinct().order_by(Curso.nombre).all()

    # Context for the template
    contexto = {
        'lista_cursos': lista_cursos,
        'lista_asignaturas': [],
        'estudiantes': None,
        'calificaciones_dict': {},
        'curso_seleccionado': curso_id,
        'asignatura_seleccionada': asignatura_id,
        'fecha_seleccionada': fecha_str or date.today().strftime('%Y-%m-%d')
    }
    
    if curso_id and asignatura_id:
        # Check if a valid assignment exists for the active year
        asignacion = Asignacion.query.filter_by(
            id_curso=curso_id,
            id_asignatura=asignatura_id,
            estado='activo',
            anio_lectivo=anio_lectivo
        ).first()

        if not asignacion:
            flash('No existe una asignación activa para este curso y asignatura en el año lectivo actual.', 'warning')
            return render_template('views/estudiantes/calificacion.html', **contexto)

        # Check permissions for non-admin users
        if not current_user.is_admin() and asignacion.id_docente != current_user.id:
            flash('No tiene permisos para calificar en esta asignación.', 'danger')
            return render_template('views/estudiantes/calificacion.html', **contexto)

        # Build the query for students SOLO del año lectivo activo
        estudiantes_query = Matricula.query.filter_by(id_curso=curso_id, estado='activo', año_lectivo=anio_lectivo)
        if busqueda:
            estudiantes_query = estudiantes_query.filter(
                (Matricula.nombres.ilike(f'%{busqueda}%')) |
                (Matricula.apellidos.ilike(f'%{busqueda}%')) |
                (Matricula.documento.ilike(f'%{busqueda}%'))
            )

        estudiantes = estudiantes_query.order_by(Matricula.apellidos, Matricula.nombres).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        contexto['estudiantes'] = estudiantes

        # Get existing grades in a single query
        calificaciones = Calificacion.query.filter_by(
            id_asignacion=asignacion.id,
            fecha_calificacion=datetime.strptime(contexto['fecha_seleccionada'], '%Y-%m-%d').date()
        ).all()

        contexto['calificaciones_dict'] = {c.id_matricula: c for c in calificaciones}

    # Load subjects for the filter dropdown if a course is selected and year active
    if curso_id:
        asignaturas_query = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        )
        if not current_user.is_admin():
            asignaturas_query = asignaturas_query.filter(Asignacion.id_docente == current_user.id)

        contexto['lista_asignaturas'] = asignaturas_query.distinct().order_by(Asignatura.nombre).all()
    
    return render_template('views/estudiantes/calificacion.html', **contexto)

@calificacion_bp.route('/guardar', methods=['POST'])
@roles_required('admin', 'docente')
def guardar_calificaciones():
    try:
        current_app.logger.debug("Starting guardar_calificaciones")
        curso_id = request.form.get('curso', type=int)
        asignatura_id = request.form.get('asignatura', type=int)
        fecha_str = request.form.get('fecha')
        busqueda = request.form.get('busqueda', '')

        if not all([curso_id, asignatura_id, fecha_str]):
            current_app.logger.debug("Missing parameters for grades.")
            flash("Error: Faltan parámetros de calificación.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        current_app.logger.debug(f"Parsed date: {fecha}")

        active_config = get_active_config()
        if not active_config:
            current_app.logger.debug("No active academic year configured.")
            flash("No hay un año lectivo configurado como activo", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
        anio_lectivo = active_config['anio']
        periodo_id = get_active_period_id()
        current_app.logger.debug(f"Active academic year: {anio_lectivo}, Period ID: {periodo_id}")

        active_anio_periodo = AnioPeriodo.query.filter_by(
            anio_lectivo=anio_lectivo,
            periodo_id=periodo_id,
            estado='activo'
        ).first()

        if not active_anio_periodo:
            current_app.logger.debug("No active period found for current academic year.")
            flash("No se encontró un período activo para el año lectivo actual.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        try:
            periodo_start_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
            periodo_end_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_fin}", "%Y-%m-%d").date()
            current_app.logger.debug(f"Period start date: {periodo_start_date}, Period end date: {periodo_end_date}")
        except ValueError as ve:
            current_app.logger.error(f"Invalid period date format: {ve}", exc_info=True)
            flash("Error: Formato de fecha de período inválido en la configuración del sistema.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        current_app.logger.debug(f"Validando fecha: {fecha}, Periodo Inicio: {periodo_start_date}, Periodo Fin: {periodo_end_date}")
        if not (periodo_start_date <= fecha <= periodo_end_date):
            db.session.rollback()
            flash(f"La fecha de calificación ({fecha_str}) debe estar dentro del período activo ({active_anio_periodo.periodo.nombre}: {active_anio_periodo.fecha_inicio} - {active_anio_periodo.fecha_fin}) del año lectivo {anio_lectivo}.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        asignacion = Asignacion.query.filter_by(
            id_curso=curso_id,
            id_asignatura=asignatura_id,
            estado='activo',
            anio_lectivo=anio_lectivo
        ).first()
        current_app.logger.debug(f"Assignment found: {asignacion is not None}")

        if not asignacion:
            current_app.logger.debug("No active assignment found.")
            flash("No se encontró una asignación activa para este curso y asignatura.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
        
        if not current_user.is_admin() and asignacion.id_docente != current_user.id:
            current_app.logger.debug("Permission denied for assignment.")
            flash("No tiene permisos para guardar calificaciones en esta asignación.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
            
        estudiantes_afectados = 0
        
        # Iterate over form data to find all grades
        for key, value in request.form.items():
            if key.startswith('calificacion_'):
                matricula_id = key.split('_')[1]
                current_app.logger.debug(f"Processing grade for matricula_id: {matricula_id}")
                
                # Validate and convert note
                try:
                    nota = float(value) if value else None
                    if nota is not None and (nota < 0 or nota > 5):
                        flash(f'Error: La calificación para el estudiante {matricula_id} debe estar entre 0 y 5.', 'danger')
                        db.session.rollback()
                        current_app.logger.debug(f"Invalid grade value for {matricula_id}: {nota}")
                        return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
                    if nota is not None and nota == 0:
                        flash(f'Error: La calificación para el estudiante {matricula_id} debe ser mayor a 0.', 'danger')
                        db.session.rollback()
                        current_app.logger.debug(f"Grade 0 not allowed for {matricula_id}")
                        return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
                except ValueError:
                    flash(f'Error: La calificación para el estudiante {matricula_id} no es un número válido.', 'danger')
                    db.session.rollback()
                    current_app.logger.debug(f"Non-numeric grade for {matricula_id}: {value}")
                    return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

                observacion = request.form.get(f'observacion_{matricula_id}', '')

                # Mover todo el procesamiento de calificaciones dentro del bloque if
                try:
                    calificacion = Calificacion.query.filter_by(
                        id_matricula=matricula_id,
                        id_asignacion=asignacion.id,
                        fecha_calificacion=fecha
                    ).first()
                    
                    if calificacion:
                        calificacion.nota = nota
                        calificacion.observacion = observacion
                        calificacion.actualizado_por = current_user.id
                        calificacion.actualizado_en = datetime.utcnow()
                        current_app.logger.debug(f"Updating grade for {matricula_id}")
                    else:
                        nueva_calificacion = Calificacion(
                            id_matricula=matricula_id,
                            id_asignacion=asignacion.id,
                            id_periodo=periodo_id,
                            fecha_calificacion=fecha,
                            nota=nota,
                            observacion=observacion,
                            creado_por=current_user.id
                        )
                        db.session.add(nueva_calificacion)
                        current_app.logger.debug(f"Adding new grade for {matricula_id}")
                    
                    estudiantes_afectados += 1
                    
                except Exception as e:
                    current_app.logger.error(f"Error during DB operation for matricula {matricula_id}: {e}", exc_info=True)
                    flash("Error al procesar calificaciones en la base de datos.", 'danger')
                    return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        current_app.logger.debug("Attempting to commit grades to DB.")
        try:
            db.session.commit()
            current_app.logger.debug("Grades committed successfully.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing grades to DB: {e}", exc_info=True)
            flash("Error al guardar las calificaciones en la base de datos.", 'danger')
            return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

        try:
            current_app.logger.debug("Attempting to save activity log.")
            if estudiantes_afectados > 0:
                actividad = Actividad(
                    tipo='calificacion',
                    titulo=f'Registro de calificaciones',
                    detalle=f"Se registraron calificaciones para {estudiantes_afectados} estudiantes en la asignatura {asignacion.asignatura.nombre} del curso {asignacion.curso.nombre}",
                    fecha=datetime.utcnow().date(),
                    creado_por=current_user.id,
                    id_asignacion=asignacion.id
                )
                existing = Actividad.query.filter_by(
                    tipo=actividad.tipo,
                    titulo=actividad.titulo,
                    detalle=actividad.detalle,
                    fecha=actividad.fecha,
                    id_asignacion=actividad.id_asignacion
                ).first()
                if not existing:
                    db.session.add(actividad)
                    db.session.commit()
                    current_app.logger.debug("Activity log saved successfully.")
                else:
                    current_app.logger.debug("Activity log already exists, skipping.")
        except Exception as e:
            current_app.logger.error(f"Error saving activity for grades: {str(e)}", exc_info=True)

        flash('Calificaciones guardadas exitosamente.', 'success')
        return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unhandled error saving grades: {str(e)}", exc_info=True)
        flash("Error interno al guardar las calificaciones.", 'danger')
        return redirect(url_for('calificacion.index', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))