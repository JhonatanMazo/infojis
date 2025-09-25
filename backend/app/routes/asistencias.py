import json
from datetime import datetime, date
from flask import Blueprint, redirect, request, jsonify, render_template, flash, current_app, url_for
from flask_login import current_user
from app.utils.decorators import roles_required
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import Asistencia, Asignacion, Matricula, Curso, Asignatura, AnioPeriodo, Actividad, User
from app.services.configuracion_service import get_active_config, get_active_period_id

asistencias_bp = Blueprint('asistencias', __name__, url_prefix='/asistencias')

@asistencias_bp.route('/asignaturas')
@roles_required('admin', 'docente')
def obtener_asignaturas():
    curso_id = request.args.get('curso_id', type=int)
    
    if not curso_id:
        return jsonify({"error": "Se requiere el ID del curso"}), 400
    
    try:
        # Obtener año lectivo activo
        config = get_active_config()
        if not config:
            return jsonify({"error": "No hay un año lectivo configurado como activo"}), 400
        anio_lectivo = config['anio']
        periodo_id = get_active_period_id()

        # Obtener asignaturas para el curso y año lectivo según el rol del usuario
        asignaturas_query = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        )

        if not current_user.is_admin():
            asignaturas_query = asignaturas_query.filter(Asignacion.id_docente == current_user.id)

        asignaturas = asignaturas_query.distinct().all()

        return jsonify([{
            'id': a.id,
            'nombre': a.nombre
        } for a in asignaturas])

    except Exception as e:
        current_app.logger.error(f"Error obteniendo asignaturas: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno al obtener asignaturas"}), 500

@asistencias_bp.route('/')
@roles_required('admin', 'docente')
def listar_asistencias():
    # Obtener parámetros de filtro
    curso_id = request.args.get('curso', type=int)
    asignatura_id = request.args.get('asignatura', type=int)
    fecha_str = request.args.get('fecha')
    busqueda = request.args.get('busqueda', '', type=str).strip()
    page = request.args.get('page', 1, type=int)
    
    # Manejo de fechas con validación
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        if fecha > date.today():
            flash('No se pueden registrar asistencias para fechas futuras', 'warning')
            fecha = date.today()
    except ValueError:
        flash('Formato de fecha inválido, usando fecha actual', 'warning')
        fecha = date.today()
    
    # Obtener configuración activa
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))

    anio_lectivo = active_config.get('anio')
    config = get_active_config()

    anio_lectivo = config['anio']
    periodo_id = get_active_period_id()

    # Obtener cursos disponibles según el rol y año lectivo activo
    cursos_query = Curso.query.join(Asignacion).filter(
        Asignacion.estado == 'activo',
        Asignacion.anio_lectivo == anio_lectivo
    )
    if not current_user.is_admin():
        cursos_query = cursos_query.filter(Asignacion.id_docente == current_user.id)
    cursos = cursos_query.distinct().all()

    # Variables para el template
    contexto = {
        'lista_cursos': cursos,
        'lista_asignaturas': [],
        'curso_seleccionado': None,
        'asignatura_seleccionada': None,
        'estudiantes': None,
        'asistencias_dict': {},
        'fecha': fecha,
    }

    # Si hay filtros aplicados
    if curso_id and asignatura_id:
        # Validar que el curso existe
        curso_seleccionado = Curso.query.get(curso_id)
        if not curso_seleccionado:
            flash('Curso no encontrado', 'danger')
            return render_template('views/estudiantes/asistencias.html', **contexto)

        contexto['curso_seleccionado'] = curso_seleccionado
        contexto['asignatura_seleccionada'] = Asignatura.query.get(asignatura_id)

        # Verificar asignación
        asignacion = Asignacion.query.filter(
            Asignacion.id_curso == curso_id,
            Asignacion.id_asignatura == asignatura_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).first()

        if not asignacion:
            flash('No existe una asignación activa para este curso y asignatura', 'warning')
        elif not current_user.is_admin() and asignacion.id_docente != current_user.id:
            flash('No tienes permisos para acceder a esta asignación', 'danger')
        else:
            # Obtener estudiantes matriculados (paginado) SOLO del año lectivo activo
            estudiantes_query = Matricula.query.filter_by(
                id_curso=curso_id,
                estado='activo',
                año_lectivo=anio_lectivo
            )
            if busqueda:
                from sqlalchemy import or_
                estudiantes_query = estudiantes_query.filter(
                    or_(
                        Matricula.nombres.ilike(f"%{busqueda}%"),
                        Matricula.apellidos.ilike(f"%{busqueda}%"),
                        Matricula.documento.ilike(f"%{busqueda}%")
                    )
            )
            estudiantes = estudiantes_query.order_by(Matricula.apellidos, Matricula.nombres).paginate(
                page=page,
                per_page=10,
                error_out=False
            )
            contexto['estudiantes'] = estudiantes

            # Obtener asistencias existentes en una sola consulta
            asistencias = Asistencia.query.filter(
                Asistencia.id_asignacion == asignacion.id,
                Asistencia.fecha == fecha
            ).all()

            contexto['asistencias_dict'] = {a.id_matricula: a for a in asistencias}

    # Cargar asignaturas solo si hay un curso seleccionado y del año lectivo activo
    if curso_id:
        asignaturas_query = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        )

        if not current_user.is_admin():
            asignaturas_query = asignaturas_query.filter(Asignacion.id_docente == current_user.id)

        contexto['lista_asignaturas'] = asignaturas_query.distinct().all()

    return render_template('views/estudiantes/asistencias.html', **contexto)


@asistencias_bp.route('/guardar', methods=['POST'])
@roles_required('admin', 'docente')
def guardar_asistencias():
    current_app.logger.debug("Starting guardar_asistencias")
    curso_id = request.form.get('curso_id', type=int)
    asignatura_id = request.form.get('asignatura_id', type=int)
    fecha_str = request.form.get('fecha')
    busqueda = request.form.get('busqueda', '')
    
    # Obtener página actual para mantener la paginación
    page = request.form.get('page', 1, type=int)

    current_app.logger.debug(f"Received data: curso_id={curso_id}, asignatura_id={asignatura_id}, fecha_str={fecha_str}, busqueda={busqueda}")

    # Validaciones básicas
    if not all([curso_id, asignatura_id, fecha_str]):
        message = "Error: Datos incompletos para guardar asistencias."
        current_app.logger.warning(f"Validation failed: Incomplete data. curso_id={curso_id}, asignatura_id={asignatura_id}, fecha_str={fecha_str}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': message}), 400
        else:
            flash(message, 'danger')
            return redirect(url_for('asistencias.listar_asistencias',
                                   curso=curso_id if curso_id else '',
                                   asignatura=asignatura_id if asignatura_id else '',
                                   fecha=fecha_str if fecha_str else '',
                                   busqueda=busqueda,
                                   page=page))
    
    try:
        # Validar fecha
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        if fecha > date.today():
            message = "Error: No se pueden registrar asistencias para fechas futuras"
            current_app.logger.warning(f"Validation failed: Future date. fecha={fecha}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': message}), 400
            else:
                flash(message, 'danger')
                return redirect(url_for('asistencias.listar_asistencias',
                                       curso=curso_id,
                                       asignatura=asignatura_id,
                                       fecha=fecha_str,
                                       busqueda=busqueda,
                                       page=page))
        current_app.logger.debug(f"Date validation passed: fecha={fecha}")

        # Obtener configuración activa
        config = get_active_config()
        if not config:
            current_app.logger.error("Validation failed: No active academic year configured.")
            flash("Error: No hay un año lectivo configurado como activo", 'danger')
            return redirect(url_for('asistencias.listar_asistencias', 
                                   curso=curso_id, 
                                   asignatura=asignatura_id, 
                                   fecha=fecha_str, 
                                   busqueda=busqueda,
                                   page=page))
        anio_lectivo = config['anio']
        current_app.logger.debug(f"Active config found: anio_lectivo={anio_lectivo}")

        periodo_id = get_active_period_id()
        current_app.logger.debug(f"Active period ID: {periodo_id}")

        # Obtener el objeto AnioPeriodo activo para validar la fecha
        active_anio_periodo = AnioPeriodo.query.filter_by(
            anio_lectivo=anio_lectivo,
            periodo_id=periodo_id,
            estado='activo'
        ).first()

        if not active_anio_periodo:
            flash("No se encontró un período activo para el año lectivo actual.", 'danger')
            current_app.logger.warning(f"Validation failed: No active period found for anio_lectivo={anio_lectivo}, periodo_id={periodo_id}")
            return redirect(url_for('asistencias.listar_asistencias', 
                                   curso=curso_id, 
                                   asignatura=asignatura_id, 
                                   fecha=fecha_str, 
                                   busqueda=busqueda,
                                   page=page))
        current_app.logger.debug(f"Active period object found: {active_anio_periodo.periodo.nombre}")

        # Convertir fechas de inicio y fin del período a objetos date
        try:
            periodo_start_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
            periodo_end_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_fin}", "%Y-%m-%d").date()
        except ValueError:
            current_app.logger.error(f"Error converting period dates. anio_lectivo={anio_lectivo}, fecha_inicio={active_anio_periodo.fecha_inicio}, fecha_fin={active_anio_periodo.fecha_fin}", exc_info=True)
            flash("Error: Formato de fecha de período inválido en la configuración del sistema.", 'danger')
            return redirect(url_for('asistencias.listar_asistencias', 
                                   curso=curso_id, 
                                   asignatura=asignatura_id, 
                                   fecha=fecha_str, 
                                   busqueda=busqueda,
                                   page=page))
        current_app.logger.debug(f"Period dates: start={periodo_start_date}, end={periodo_end_date}")

        # Validar que la fecha de asistencia esté dentro del período activo
        current_app.logger.debug(f"Validando fecha: {fecha}, Periodo Inicio: {periodo_start_date}, Periodo Fin: {periodo_end_date}")
        if not (periodo_start_date <= fecha <= periodo_end_date):
            db.session.rollback()
            message = f"La fecha de asistencia ({fecha_str}) debe estar dentro del período activo ({active_anio_periodo.periodo.nombre}: {active_anio_periodo.fecha_inicio} - {active_anio_periodo.fecha_fin}) del año lectivo {anio_lectivo}."
            current_app.logger.warning(f"Validation failed: Attendance date {fecha} outside active period {periodo_start_date}-{periodo_end_date}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': message}), 400
            else:
                flash(message, 'danger')
                return redirect(url_for('asistencias.listar_asistencias',
                                       curso=curso_id,
                                       asignatura=asignatura_id,
                                       fecha=fecha_str,
                                       busqueda=busqueda,
                                       page=page))
        current_app.logger.debug("Attendance date within active period.")

        # Validar asignación
        asignacion = Asignacion.query.filter_by(
            id_asignatura=asignatura_id,
            id_curso=curso_id,
            estado='activo',
            anio_lectivo=anio_lectivo
        ).first()

        if not asignacion:
            flash("Error: No existe una asignación activa para este curso y asignatura", 'danger')
            current_app.logger.warning(f"Validation failed: No active assignment found for asignatura_id={asignatura_id}, curso_id={curso_id}, anio_lectivo={anio_lectivo}")
            return redirect(url_for('asistencias.listar_asistencias', 
                                   curso=curso_id, 
                                   asignatura=asignatura_id, 
                                   fecha=fecha_str, 
                                   busqueda=busqueda,
                                   page=page))
        current_app.logger.debug(f"Assignment found: {asignacion.id}")

        # Verificar permisos
        if not current_user.is_admin() and asignacion.id_docente != current_user.id:
            flash("Error: No tiene permisos para guardar asistencias en esta asignación.", 'danger')
            current_app.logger.warning(f"Permission denied: User {current_user.id} tried to save attendance for assignment {asignacion.id} (docente: {asignacion.id_docente})")
            return redirect(url_for('asistencias.listar_asistencias', 
                                   curso=curso_id, 
                                   asignatura=asignatura_id, 
                                   fecha=fecha_str, 
                                   busqueda=busqueda,
                                   page=page))
        current_app.logger.debug("Permissions checked and granted.")

        # Estados válidos
        estados_validos = {'presente', 'ausente', 'justificado'}

        estudiantes_afectados = 0

        # Procesar cada asistencia
        asistencias_data_list = json.loads(request.form.get('asistencias_json', '[]'))
        current_app.logger.debug(f"Processing asistencias_json: {asistencias_data_list}")

        for asistencia_data in asistencias_data_list:
            current_app.logger.debug(f"Processing attendance data: {asistencia_data}")
            if 'matricula_id' not in asistencia_data or 'estado' not in asistencia_data:
                current_app.logger.warning(f"Skipping attendance data due to missing matricula_id or estado: {asistencia_data}")
                continue
            matricula_id = asistencia_data['matricula_id']
            estado = asistencia_data['estado']
            observacion = asistencia_data.get('observacion', '')
            
            if estado not in estados_validos:
                current_app.logger.warning(f"Skipping attendance data due to invalid state '{estado}': {asistencia_data}")
                continue
            
            matricula = Matricula.query.filter_by(
                id=matricula_id,
                id_curso=curso_id,
                estado='activo',
                año_lectivo=anio_lectivo
            ).first()
            if not matricula:
                current_app.logger.warning(f"Skipping attendance data: Matricula {matricula_id} not found or inactive for curso {curso_id}, anio {anio_lectivo}")
                continue
            current_app.logger.debug(f"Matricula found for ID: {matricula_id}")

            asistencia = Asistencia.query.filter_by(
                id_matricula=matricula_id,
                id_asignacion=asignacion.id,
                fecha=fecha
            ).first()

            if asistencia:
                current_app.logger.debug(f"Updating existing attendance for matricula {matricula_id}")
                asistencia.estado = estado
                asistencia.observaciones = observacion[:500]
                asistencia.actualizado_por = current_user.id
                asistencia.actualizado_en = datetime.utcnow()
            else:
                current_app.logger.debug(f"Creating new attendance for matricula {matricula_id}")
                asistencia = Asistencia(
                    id_matricula=matricula_id,
                    id_asignacion=asignacion.id,
                    fecha=fecha,
                    estado=estado,
                    observaciones=observacion[:500],
                    creado_por=current_user.id
                )
                db.session.add(asistencia)
            
            estudiantes_afectados += 1
            current_app.logger.debug(f"Attendance processed for matricula {matricula_id}. Total affected: {estudiantes_afectados}")

        current_app.logger.debug("Attempting to commit changes to database.")
        db.session.commit()
        current_app.logger.debug("Changes committed successfully.")

        # Crear una sola actividad para el registro masivo
        try:
            if estudiantes_afectados > 0:
                actividad = Actividad(
                    tipo='asistencia',
                    titulo=f'Registro de asistencias',
                    detalle=f"Se registraron asistencias para {estudiantes_afectados} estudiantes en la asignatura {asignacion.asignatura.nombre} del curso {asignacion.curso.nombre}",
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
                    current_app.logger.debug(f"Activity log created for {estudiantes_afectados} students.")
                else:
                    current_app.logger.debug("Activity log already exists, skipping.")
        except Exception as e:
            current_app.logger.error(f"Error saving activity for attendances: {str(e)}", exc_info=True)
            # No retornar error ya que las asistencias ya están guardadas

        # Flash message de éxito - CORREGIDO para mostrar mensajes
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Asistencias guardadas correctamente'})
        else:
            flash(f"Asistencias guardadas correctamente", 'success')
        current_app.logger.info(f"Successfully saved attendances.")

        # Redirigir manteniendo todos los parámetros - CORREGIDO
        return redirect(url_for('asistencias.listar_asistencias',
                               curso=curso_id,
                               asignatura=asignatura_id,
                               fecha=fecha_str,
                               busqueda=busqueda,
                               page=page))

    except ValueError as e:
        flash("Error: Formato de fecha inválido", 'danger')
        current_app.logger.error(f"ValueError in guardar_asistencias: {str(e)}", exc_info=True)
        return redirect(url_for('asistencias.listar_asistencias', 
                               curso=curso_id if curso_id else '', 
                               asignatura=asignatura_id if asignatura_id else '', 
                               fecha=fecha_str if fecha_str else '', 
                               busqueda=busqueda,
                               page=page))
    except Exception as e:
        db.session.rollback()
        flash("Error interno al guardar asistencias", 'danger')
        current_app.logger.error(f"Unhandled exception in guardar_asistencias: {str(e)}", exc_info=True)
        return redirect(url_for('asistencias.listar_asistencias', 
                               curso=curso_id if curso_id else '', 
                               asignatura=asignatura_id if asignatura_id else '', 
                               fecha=fecha_str if fecha_str else '', 
                               busqueda=busqueda,
                               page=page))



@asistencias_bp.route('/observacion', methods=['POST'])
@asistencias_bp.route('/observacion/<int:asistencia_id>', methods=['PUT'])
@roles_required('admin', 'docente')
def gestionar_observacion(asistencia_id=None):
    
    # Obtener parámetros de filtro
    curso_id = request.args.get('curso', type=int)
    asignatura_id = request.args.get('asignatura', type=int)
    fecha_str = request.args.get('fecha')
    busqueda = request.args.get('busqueda', '', type=str).strip()
    
    
    # Validar JSON
    if not request.is_json:
        return jsonify({"error": "Se requiere Content-Type: application/json"}), 400
        
    data = request.get_json()
    
    # Validar datos mínimos
    if not data or 'matricula_id' not in data:
        return jsonify({"error": "Se requiere ID de matrícula"}), 400
    
    try:
        if asistencia_id:  # Actualización PUT
            asistencia = Asistencia.query.get_or_404(asistencia_id)
            
            # Verificar permisos
            if not current_user.is_admin() and asistencia.asignacion.id_docente != current_user.id:
                return jsonify({"error": "No autorizado para modificar esta observación"}), 403
                
            # Actualizar observación
            asistencia.observaciones = data.get('observacion', '')[:500]  # Limitar longitud
            asistencia.actualizado_por = current_user.id
            asistencia.actualizado_en = datetime.utcnow()
            
        else:  # Creación POST
            # Validar parámetros requeridos
            required_params = ['asignatura_id', 'curso_id', 'fecha']
            if any(param not in request.args for param in required_params):
                return jsonify({"error": "Faltan parámetros requeridos (asignatura_id, curso_id, fecha)"}), 400
                
            # Validar fecha
            try:
                fecha = datetime.strptime(request.args.get('fecha'), '%Y-%m-%d').date()
                if fecha > date.today():
                    return jsonify({"error": "No se pueden registrar observaciones para fechas futuras"}), 400
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido (YYYY-MM-DD)"}), 400
            
            # Obtener configuración activa
            config = get_active_config()
            if not config:
                return jsonify({"error": "No hay un año lectivo configurado como activo"}), 400
            anio_lectivo = config['anio']
            periodo_id = get_active_period_id()

            # Obtener el objeto AnioPeriodo activo para validar la fecha
            active_anio_periodo = AnioPeriodo.query.filter_by(
                anio_lectivo=anio_lectivo,
                periodo_id=periodo_id,
                estado='activo'
            ).first()

            if not active_anio_periodo:
                return jsonify({"error": "No se encontró un período activo para el año lectivo actual."}), 400

            # Convertir fechas de inicio y fin del período a objetos date
            try:
                periodo_start_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
                periodo_end_date = datetime.strptime(f"{anio_lectivo}-{active_anio_periodo.fecha_fin}", "%Y-%m-%d").date()
            except ValueError:
                flash("Error: Formato de fecha de período inválido en la configuración del sistema.", 'danger')
                return redirect(url_for('asistencias.listar_asistencias', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

            # Validar que la fecha de observación esté dentro del período activo
            if not (periodo_start_date <= fecha <= periodo_end_date):
                db.session.rollback()
                flash(f"La fecha de observación ({request.args.get('fecha')}) debe estar dentro del período activo ({active_anio_periodo.periodo.nombre}: {active_anio_periodo.fecha_inicio} - {active_anio_periodo.fecha_fin}) del año lectivo {anio_lectivo}.", 'danger')
                return redirect(url_for('asistencias.listar_asistencias', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

            # Validar asignación
            asignacion = Asignacion.query.filter_by(
                id_asignatura=request.args.get('asignatura_id'),
                id_curso=request.args.get('curso_id'),
                estado='activo',
                anio_lectivo=anio_lectivo
            ).first()
            
            if not asignacion:
                flash("Error: Asignación no encontrada o inactiva.", 'danger')
                return redirect(url_for('asistencias.listar_asistencias', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))

                
            # Verificar permisos
            if not current_user.is_admin() and asignacion.id_docente != current_user.id:
                flash("Error: No autorizado para esta asignación.", 'danger')
                return redirect(url_for('asistencias.listar_asistencias', curso=curso_id, asignatura=asignatura_id, fecha=fecha_str, busqueda=busqueda))
                
            # Validar matrícula
            matricula = Matricula.query.filter_by(
                id=data['matricula_id'],
                id_curso=request.args.get('curso_id'),
                estado='activo'
            ).first()
            
            if not matricula:
                flash("Error: Estudiante no matriculado en este curso.", 'danger')
                
                
            # Crear nueva asistencia con observación
            asistencia = Asistencia(
                id_matricula=data['matricula_id'],
                id_asignacion=asignacion.id,
                fecha=fecha,
                estado='presente',  # Valor por defecto
                observaciones=data.get('observacion', '')[:500],
                creado_por=current_user.id
            )
            db.session.add(asistencia)
        
        db.session.commit()

        # Crear notificaciones para administradores si es docente
        if current_user.rol == 'docente':
            try:
                admin_users = User.query.filter_by(rol='admin', estado='activo').all()
                for admin in admin_users:
                    actividad_admin = Actividad(
                        tipo='observacion',
                        titulo='Nueva observación en asistencia',
                        detalle=f'Se registró una observación en la asistencia del estudiante {matricula.nombres} {matricula.apellidos}.',
                        fecha=datetime.utcnow().date(),
                        creado_por=current_user.id,
                        id_asignacion=asignacion.id
                    )
                    db.session.add(actividad_admin)
                db.session.commit()
            except Exception as admin_act_e:
                current_app.logger.error(f"Error creando actividad para admin en observación de asistencia: {str(admin_act_e)}")
                # No relanzar la excepción

        return jsonify({
            "success": True,
            "message": "Observación guardada correctamente",
            "asistencia_id": asistencia.id
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Error de base de datos: {str(e)}", exc_info=True)
        flash("Error: Error de base de datos al guardar observación.", 'danger')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error gestionando observación: {str(e)}", exc_info=True)
        flash("Error: Error interno al guardar observación.", 'danger')
    




# Endpoint para obtener la observación actual de una asistencia (AJAX)
@asistencias_bp.route('/observacion/<int:asistencia_id>', methods=['GET'])
@roles_required('admin', 'docente')
def obtener_observacion(asistencia_id):
    """Devuelve la observación actual de una asistencia por ID (AJAX)."""
    asistencia = Asistencia.query.get_or_404(asistencia_id)
    # Permisos: solo admin o docente asignado
    if not current_user.is_admin() and asistencia.asignacion.id_docente != current_user.id:
        return jsonify({"success": False, "error": "No autorizado"}), 403
    return jsonify({"success": True, "observacion": asistencia.observaciones or ''}) 
