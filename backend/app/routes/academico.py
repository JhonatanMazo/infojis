from io import BytesIO
from flask import Blueprint, current_app, redirect, render_template, request, jsonify, url_for, flash, make_response
from flask_login import current_user
from app import db
from app.models import Matricula, Curso, Asignatura, Asistencia, Calificacion, Asignacion, User
from app.utils.decorators import roles_required
from sqlalchemy import func
from app.models.configuracion_libro import ConfiguracionLibro
from datetime import datetime as dt
from sqlalchemy.orm import joinedload
from app.models.anio_periodo import AnioPeriodo
# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os
from app.services.configuracion_service import get_active_config

academico_bp = Blueprint('academico', __name__, url_prefix='/informes/academico')

@academico_bp.route('/')
@roles_required('admin', 'docente')
def index():
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']

    # Obtener período activo
    active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, estado='activo').first()
    start_date = None
    end_date = None
    if active_anio_periodo:
        start_date = dt(anio_lectivo, int(active_anio_periodo.fecha_inicio.split('-')[0]), int(active_anio_periodo.fecha_inicio.split('-')[1]))
        end_date = dt(anio_lectivo, int(active_anio_periodo.fecha_fin.split('-')[0]), int(active_anio_periodo.fecha_fin.split('-')[1]))

    curso_id = request.args.get('curso', type=int)
    asignatura_id = request.args.get('asignatura', type=int)
    tipo = request.args.get('tipo')
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('busqueda', '').strip()
    per_page = 10
    
    if current_user.rol == 'admin':
        # Para admin: todos los cursos con matrículas activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []

    else:
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().order_by(Curso.nombre).all()

    asignaturas = []
    if curso_id:
        if current_user.rol != 'admin':
            asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id, anio_lectivo=anio_lectivo).first()
            if not asignacion:
                flash('No tiene permisos para ver este curso.', 'danger')
                return redirect(url_for('academico.index'))
        asignaturas = Asignatura.query.join(Asignacion).filter(
            Asignacion.id_curso == curso_id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().order_by(Asignatura.nombre).all()
    
    query = Matricula.query.filter_by(estado='activo', año_lectivo=anio_lectivo)
    
    if curso_id:
        query = query.filter_by(id_curso=curso_id)
    elif current_user.rol != 'admin':
        cursos_docente_ids = [c.id for c in cursos]
        query = query.filter(Matricula.id_curso.in_(cursos_docente_ids))

    if busqueda:
        from sqlalchemy import or_
        search_term = f"%{busqueda}%"
        query = query.filter(
            or_(
                Matricula.nombres.ilike(search_term),
                Matricula.apellidos.ilike(search_term)
            )
        )
    
    estudiantes = query.order_by(Matricula.apellidos, Matricula.nombres).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    estadisticas_asistencia = {}
    observaciones_count = {}
    calificaciones_estudiantes = {}
    promedios_estudiantes = {}
    asignaturas_anio = []
    

    if tipo == 'asistencia' and asignatura_id:
        for estudiante in estudiantes.items:
            query = db.session.query(
                Asistencia.estado,
                func.count(Asistencia.id).label('cantidad')
            ).join(Asignacion).filter(
                Asistencia.id_matricula == estudiante.id,
                Asignacion.id_asignatura == asignatura_id,
                Asignacion.anio_lectivo == anio_lectivo
            )
            if start_date and end_date:
                query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
            stats = query.group_by(Asistencia.estado).all()
            
            estadisticas = {'presente': 0, 'ausente': 0, 'justificado': 0}
            for stat in stats:
                estadisticas[stat.estado] = stat.cantidad
            
            estadisticas_asistencia[estudiante.id] = estadisticas
            
            query_obs = db.session.query(func.count(Asistencia.id)).join(Asignacion).filter(
                Asistencia.id_matricula == estudiante.id,
                Asignacion.id_asignatura == asignatura_id,
                Asignacion.anio_lectivo == anio_lectivo,
                Asistencia.observaciones != None,
                Asistencia.observaciones != ''
            )
            if start_date and end_date:
                query_obs = query_obs.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)
            count = query_obs.scalar()
            
            observaciones_count[estudiante.id] = count or 0

    elif tipo == 'calificaciones':
        if curso_id:
            asignaturas_anio = Asignatura.query.join(Asignacion).filter(
                Asignacion.id_curso == curso_id,
                Asignacion.estado == 'activo',
                Asignacion.anio_lectivo == anio_lectivo
            ).distinct().order_by(Asignatura.nombre).all()
        
            for estudiante in estudiantes.items:
                calificaciones = {}
                promedio_total = 0
                count_calificaciones = 0
                
                for asignatura in asignaturas_anio:
                    if asignatura_id and asignatura.id != asignatura_id:
                        continue
                    query_cal = db.session.query(func.avg(Calificacion.nota)).join(Asignacion).filter(
                        Calificacion.id_matricula == estudiante.id,
                        Asignacion.id_asignatura == asignatura.id,
                        Asignacion.anio_lectivo == anio_lectivo,
                        Calificacion.nota.isnot(None)
                    )
                    if start_date and end_date:
                        query_cal = query_cal.filter(Calificacion.fecha_calificacion >= start_date, Calificacion.fecha_calificacion <= end_date)
                    promedio = query_cal.scalar()
                    
                    if promedio:
                        calificaciones[asignatura.id] = round(promedio, 1)
                        promedio_total += promedio
                        count_calificaciones += 1
                
                calificaciones_estudiantes[estudiante.id] = calificaciones
                
                if count_calificaciones > 0:
                    promedios_estudiantes[estudiante.id] = round(promedio_total / count_calificaciones, 1)
                
    config_libro = ConfiguracionLibro.obtener_configuracion_actual()
            
    
    return render_template('views/informes/academicos.html',
        estudiantes=estudiantes,
        cursos=cursos,
        asignaturas=asignaturas,
        curso_seleccionado=curso_id,
        curso_seleccionado_obj=Curso.query.get(curso_id) if curso_id else None,
        asignatura_seleccionada=asignatura_id,
        asignatura_seleccionada_obj=Asignatura.query.get(asignatura_id) if asignatura_id else None,
        tipo_seleccionado=tipo,
        estadisticas_asistencia=estadisticas_asistencia,
        observaciones_count=observaciones_count,
        calificaciones_estudiantes=calificaciones_estudiantes,
        promedios_estudiantes=promedios_estudiantes,
        asignaturas_anio=asignaturas_anio,
        config_libro=config_libro,
        active_config=active_config)


@academico_bp.route('/obtener_observaciones')
@roles_required('admin', 'docente')
def obtener_observaciones():
    active_config = get_active_config()
    if not active_config:
        return jsonify({'error': 'No hay un año lectivo configurado como activo'}), 400

    anio_lectivo = active_config['anio']

    estudiante_id = request.args.get('estudiante_id', type=int)
    asignatura_id = request.args.get('asignatura_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if not estudiante_id:
        return jsonify({'error': 'ID de estudiante requerido'}), 400

    # Si no se proporciona asignatura_id, intentar obtenerlo del referrer (página académica)
    if not asignatura_id and request.referrer:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(request.referrer)
        query = parse_qs(parsed.query)
        asignatura_id_str = query.get('asignatura', [None])[0]
        if asignatura_id_str:
            try:
                asignatura_id = int(asignatura_id_str)
            except ValueError:
                pass

    if current_user.rol != 'admin':
        matricula = Matricula.query.get_or_404(estudiante_id)
        asignacion = Asignacion.query.filter_by(id_curso=matricula.id_curso, id_docente=current_user.id).first()
        if not asignacion:
            return jsonify({'error': 'No tiene permisos para ver estas observaciones.'}), 403



    query = db.session.query(
        Asistencia.fecha,
        Asistencia.observaciones,
        Asistencia.estado,
        User.nombre.label('profesor_nombre'),
        User.apellidos.label('profesor_apellidos'),
        Asignatura.nombre.label('asignatura_nombre')
    ).select_from(Asistencia).join(
        Asignacion, Asistencia.id_asignacion == Asignacion.id
    ).join(
        Asignatura, Asignacion.id_asignatura == Asignatura.id
    ).outerjoin(
        User, Asistencia.creado_por == User.id
    ).filter(
        Asistencia.id_matricula == estudiante_id,
        Asignacion.anio_lectivo == anio_lectivo,
        Asistencia.observaciones != None,
        Asistencia.observaciones != ''
    )
    if asignatura_id:
        query = query.filter(Asignacion.id_asignatura == asignatura_id)

    active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, estado='activo').first()
    if active_anio_periodo:
        start_date = dt(anio_lectivo, int(active_anio_periodo.fecha_inicio.split('-')[0]), int(active_anio_periodo.fecha_inicio.split('-')[1]))
        end_date = dt(anio_lectivo, int(active_anio_periodo.fecha_fin.split('-')[0]), int(active_anio_periodo.fecha_fin.split('-')[1]))
        query = query.filter(Asistencia.fecha >= start_date, Asistencia.fecha <= end_date)

    observaciones = query.order_by(Asistencia.fecha.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    resultados = []
    for obs in observaciones.items:
        profesor_nombre = "Sistema"
        if obs.profesor_nombre and obs.profesor_apellidos:
            profesor_nombre = f"{obs.profesor_nombre} {obs.profesor_apellidos}"
        elif obs.profesor_nombre:
            profesor_nombre = obs.profesor_nombre

        resultados.append({
            'fecha': obs.fecha.isoformat(),
            'observacion': obs.observaciones,
            'estado': obs.estado,
            'asignatura': obs.asignatura_nombre,
            'registrado_por': profesor_nombre
        })

    return jsonify({
        'observaciones': resultados,
        'pagina': page,
        'total_paginas': observaciones.pages,
        'total_registros': observaciones.total
    })

@academico_bp.route('/obtener_calificaciones')
@roles_required('admin', 'docente')
def obtener_calificaciones():
    try:
        active_config = get_active_config()
        if not active_config:
            return jsonify({'error': 'No hay un año lectivo configurado como activo'}), 400

        anio_lectivo = active_config['anio']

        estudiante_id = request.args.get('estudiante_id', type=int)
        asignatura_id = request.args.get('asignatura_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        if not estudiante_id:
            return jsonify({'error': 'ID de estudiante requerido'}), 400

        # Si no se proporciona asignatura_id, intentar obtenerlo del referrer (página académica)
        if not asignatura_id and request.referrer:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(request.referrer)
            query = parse_qs(parsed.query)
            asignatura_id_str = query.get('asignatura', [None])[0]
            if asignatura_id_str:
                try:
                    asignatura_id = int(asignatura_id_str)
                except ValueError:
                    pass

        if current_user.rol != 'admin':
            matricula = Matricula.query.get_or_404(estudiante_id)
            asignacion = Asignacion.query.filter_by(id_curso=matricula.id_curso, id_docente=current_user.id).first()
            if not asignacion:
                return jsonify({'error': 'No tiene permisos para ver estas calificaciones.'}), 403



        calificaciones_query = Calificacion.query\
            .options(
                joinedload(Calificacion.asignacion).joinedload(Asignacion.docente),
                joinedload(Calificacion.asignacion).joinedload(Asignacion.asignatura)
            )\
            .join(Asignacion, Calificacion.id_asignacion == Asignacion.id)\
            .filter(
                Calificacion.id_matricula == estudiante_id,
                Asignacion.anio_lectivo == anio_lectivo
            )
        if asignatura_id:
            calificaciones_query = calificaciones_query.filter(Asignacion.id_asignatura == asignatura_id)

        active_anio_periodo = AnioPeriodo.query.filter_by(anio_lectivo=anio_lectivo, estado='activo').first()
        if active_anio_periodo:
            start_date = dt(anio_lectivo, int(active_anio_periodo.fecha_inicio.split('-')[0]), int(active_anio_periodo.fecha_inicio.split('-')[1]))
            end_date = dt(anio_lectivo, int(active_anio_periodo.fecha_fin.split('-')[0]), int(active_anio_periodo.fecha_fin.split('-')[1]))
            calificaciones_query = calificaciones_query.filter(Calificacion.fecha_calificacion >= start_date, Calificacion.fecha_calificacion <= end_date)

        calificaciones_query = calificaciones_query.order_by(Calificacion.fecha_calificacion.desc())

        calificaciones = calificaciones_query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        calificaciones_data = []
        for calificacion in calificaciones.items:
            docente_info = 'N/A'
            if (calificacion.asignacion and
                hasattr(calificacion.asignacion, 'docente') and
                calificacion.asignacion.docente):
                docente_info = f"{calificacion.asignacion.docente.nombre} {calificacion.asignacion.docente.apellidos}"

            calificaciones_data.append({
                'id': calificacion.id,
                'asignatura': calificacion.asignacion.asignatura.nombre if calificacion.asignacion and calificacion.asignacion.asignatura else 'N/A',
                'nota': calificacion.nota,
                'fecha_calificacion': calificacion.fecha_calificacion.strftime('%d/%m/%Y'),
                'observaciones': getattr(calificacion, 'observacion', '') or 'N/A',
                'docente': docente_info
            })

        return jsonify({
            'calificaciones': calificaciones_data,
            'pagination': {
                'page': calificaciones.page,
                'per_page': calificaciones.per_page,
                'total': calificaciones.total,
                'pages': calificaciones.pages,
                'has_prev': calificaciones.has_prev,
                'has_next': calificaciones.has_next,
                'prev_num': calificaciones.prev_num,
                'next_num': calificaciones.next_num
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error obteniendo calificaciones: {str(e)}", exc_info=True)
        return jsonify({'error': 'Error interno del servidor'}), 500
    
    
    
@academico_bp.route('/exportar')
@roles_required('admin', 'docente')
def exportar_datos():
    try:
        active_config = get_active_config()
        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('academico.index'))
        
        anio_lectivo = active_config['anio']

        curso_id = request.args.get('curso', type=int)
        asignatura_id = request.args.get('asignatura', type=int)
        tipo = request.args.get('tipo', 'asistencia')

        if current_user.rol != 'admin' and curso_id:
            asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id, anio_lectivo=anio_lectivo).first()
            if not asignacion:
                flash('No tiene permisos para exportar este curso.', 'danger')
                return redirect(url_for('academico.index'))
        
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        
        color_primary = HexColor("#2C3E50")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        def draw_header(titulo):
            c.setFillColor(HexColor("#FBFCFC"))
            c.rect(0, 0, width, height, fill=1, stroke=0)
            
            c.setStrokeColor(color_primary)
            c.setLineWidth(0.5)
            c.roundRect(10*mm, 10*mm, width-20*mm, height-20*mm, 5*mm, stroke=1, fill=0)
            
            try:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                logo_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
                
                if os.path.exists(logo_path):
                    c.drawImage(logo_path, margin_left, height-50*mm, width=35*mm, height=40*mm, 
                               mask='auto', preserveAspectRatio=True)
            except Exception:
                pass
            
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(black)
            c.drawCentredString(width/2, height-20*mm, "JARDÍN INFANTIL SONRISAS")
            
            c.setFont("Helvetica-Oblique", 10)
            c.setFillColor(black)
            c.drawCentredString(width/2, height-25*mm, '"Aprendiendo y sonriendo"')
            
            c.setFont("Helvetica", 9)
            c.setFillColor(black)
            c.drawCentredString(width/2, height-30*mm, "Código DANE N° 320001800766")
            c.drawCentredString(width/2, height-35*mm, "Teléfono: 300 149 8933")
            
            c.setFont("Helvetica-Bold", 20)
            c.setFillColor(black)
            c.drawCentredString(width/2, height-50*mm, titulo)
            
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            
            filtros = []
            if curso_id:
                curso = Curso.query.get(curso_id)
                filtros.append(f"Curso: {curso.nombre}")
            if asignatura_id:
                asignatura = Asignatura.query.get(asignatura_id)
                filtros.append(f"Asignatura: {asignatura.nombre}")
            
            if filtros:
                c.drawCentredString(width/2, height-58*mm, " | ".join(filtros))
            
            c.drawCentredString(width/2, height-63*mm, f"Año lectivo: {anio_lectivo}")

            return height - 70*mm
        
        def draw_footer(c, pagina_actual, total_paginas, usuario_exportador, total_registros):
            """Función auxiliar para dibujar el pie de página (igual al de cursos)"""
            width = A4[0]
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(HexColor("#777777"))
            c.drawCentredString(width/2, 30*mm, f"Reporte generado por {usuario_exportador}")
            c.drawCentredString(width/2, 25*mm, f"Fecha: {dt.now().strftime('%d/%m/%Y %H:%M')}")
            c.drawCentredString(width/2, 20*mm, f"Total registros: {total_registros}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina_actual} de {total_paginas}")
                
        if tipo == 'asistencia':
            if not asignatura_id:
                flash('Para exportar asistencias debe seleccionar una asignatura', 'warning')
                return redirect(url_for('academico.index'))
            
            query = Matricula.query.filter_by(estado='activo', año_lectivo=anio_lectivo)
            if curso_id:
                query = query.filter_by(id_curso=curso_id)
            
            estudiantes = query.order_by(Matricula.apellidos, Matricula.nombres).all()
            
            if not estudiantes:
                flash('No hay estudiantes para exportar con los filtros actuales', 'warning')
                return redirect(url_for('academico.index'))
            
            asignatura = Asignatura.query.get(asignatura_id)
            titulo_asignatura = f"REPORTE DE ASISTENCIAS" if asignatura else "REPORTE DE ASISTENCIAS"
            
            current_y = draw_header(titulo_asignatura)
            
            estudiantes_por_pagina = 20
            total_paginas = (len(estudiantes) + estudiantes_por_pagina - 1) // estudiantes_por_pagina
            
            for pagina in range(total_paginas):
                if pagina > 0:
                    c.showPage()
                    current_y = draw_header(titulo_asignatura)
                
                header_height = 8*mm
                c.setFillColor(black)
                c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
                
                available_width = width - (2 * margin_left)
                column_width = available_width / 6
                col_positions = [margin_left + (i * column_width) for i in range(6)]
                
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(white)
                headers = ["N°", "ESTUDIANTE", "DOCUMENTO", "ASISTENCIA", "INASISTENCIA", "JUSTIFICADO"]
                
                for i, header in enumerate(headers):
                    if i < len(col_positions):
                        c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
                
                current_y -= 15*mm
                
                c.setFont("Helvetica", 8)
                c.setFillColor(black)
                
                inicio = pagina * estudiantes_por_pagina
                fin = inicio + estudiantes_por_pagina
                estudiantes_pagina = estudiantes[inicio:fin]
                
                for i, estudiante in enumerate(estudiantes_pagina, inicio + 1):
                    stats = db.session.query(
                        Asistencia.estado,
                        func.count(Asistencia.id).label('cantidad')
                    ).join(Asignacion).filter(
                        Asistencia.id_matricula == estudiante.id,
                        Asignacion.id_asignatura == asignatura_id,
                        Asignacion.anio_lectivo == anio_lectivo
                    ).group_by(Asistencia.estado).all()
                    
                    estadisticas = {'presente': 0, 'ausente': 0, 'justificado': 0}
                    for stat in stats:
                        estadisticas[stat.estado] = stat.cantidad
                    
                    datos = [
                        str(i),
                        f"{estudiante.nombres} {estudiante.apellidos}"[:20] + '...' if len(f"{estudiante.nombres} {estudiante.apellidos}") > 23 else f"{estudiante.nombres} {estudiante.apellidos}",
                        estudiante.documento,
                        str(estadisticas['presente']),
                        str(estadisticas['ausente']),
                        str(estadisticas['justificado'])
                    ]
                    
                    for j, dato in enumerate(datos):
                        if j < len(col_positions):
                            c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                    
                    current_y -= 5*mm
                    
                    c.setStrokeColor(HexColor("#DDDDDD"))
                    c.setLineWidth(0.2)
                    c.line(margin_left, current_y, margin_right, current_y)
                    
                    current_y -= 4*mm
                
                draw_footer(c, pagina + 1, total_paginas, usuario_exportador, len(estudiantes))
        
        elif tipo == 'calificaciones':
            query = Matricula.query.filter_by(estado='activo', año_lectivo=anio_lectivo)
            if curso_id:
                query = query.filter_by(id_curso=curso_id)
            
            estudiantes = query.order_by(Matricula.apellidos, Matricula.nombres).all()
            
            if not estudiantes:
                flash('No hay estudiantes para exportar con los filtros actuales', 'warning')
                return redirect(url_for('academico.index'))
            
            asignaturas_anio = Asignatura.query.join(Asignacion).filter(
                Asignacion.estado == 'activo',
                Asignacion.anio_lectivo == anio_lectivo
            )
            if curso_id:
                asignaturas_anio = asignaturas_anio.filter(Asignacion.id_curso == curso_id)
            
            asignaturas_anio = asignaturas_anio.distinct().order_by(Asignatura.nombre).all()
            
            asignatura_nombre = ""
            if asignatura_id:
                asignatura = Asignatura.query.get(asignatura_id)
                if asignatura:
                    asignatura_nombre = asignatura.nombre
            
            titulo_calificaciones = f"REPORTE DE CALIFICACIONES"
            current_y = draw_header(titulo_calificaciones)
            
            estudiantes_por_pagina = 15
            total_paginas = (len(estudiantes) + estudiantes_por_pagina - 1) // estudiantes_por_pagina
            
            for pagina in range(total_paginas):
                if pagina > 0:
                    c.showPage()
                    current_y = draw_header(titulo_calificaciones)
                
                header_height = 8*mm
                c.setFillColor(black)
                c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
                
                num_columnas = 5
                column_width = (width - (2 * margin_left)) / num_columnas
                col_positions = [margin_left + (i * column_width) for i in range(num_columnas)]
                
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(white)
                headers = ["N°", "ESTUDIANTE", "DOCUMENTO", "N NOTAS", "PROMEDIO"]
                
                for i, header in enumerate(headers):
                    if i < len(col_positions):
                        c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
                
                current_y -= 15*mm
                
                c.setFont("Helvetica", 8)
                c.setFillColor(black)
                
                inicio = pagina * estudiantes_por_pagina
                fin = inicio + estudiantes_por_pagina
                estudiantes_pagina = estudiantes[inicio:fin]
                
                for i, estudiante in enumerate(estudiantes_pagina, inicio + 1):
                    total_notas = 0
                    suma_notas = 0
                    
                    for asignatura in asignaturas_anio:
                        if asignatura_id and asignatura.id != asignatura_id:
                            continue
                            
                        count = db.session.query(func.count(Calificacion.id)).join(Asignacion).filter(
                            Calificacion.id_matricula == estudiante.id,
                            Asignacion.id_asignatura == asignatura.id,
                            Asignacion.anio_lectivo == anio_lectivo,
                            Calificacion.nota.isnot(None)
                        ).scalar() or 0
                        
                        total_notas += count
                        
                        promedio = db.session.query(func.avg(Calificacion.nota)).join(Asignacion).filter(
                            Calificacion.id_matricula == estudiante.id,
                            Asignacion.id_asignatura == asignatura.id,
                            Asignacion.anio_lectivo == anio_lectivo,
                            Calificacion.nota.isnot(None)
                        ).scalar() or 0
                        
                        suma_notas += promedio * count if count > 0 else 0
                    
                    promedio_general = round(suma_notas / total_notas, 1) if total_notas > 0 else 0
                    
                    datos = [
                        str(i),
                        f"{estudiante.nombres} {estudiante.apellidos}"[:20] + '...' if len(f"{estudiante.nombres} {estudiante.apellidos}") > 23 else f"{estudiante.nombres} {estudiante.apellidos}",
                        estudiante.documento,
                        str(total_notas),
                        str(promedio_general)
                    ]
                    
                    for j, dato in enumerate(datos):
                        if j < len(col_positions):
                            c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                    
                    current_y -= 5*mm
                    
                    c.setStrokeColor(HexColor("#DDDDDD"))
                    c.setLineWidth(0.2)
                    c.line(margin_left, current_y, margin_right, current_y)
                    
                    current_y -= 4*mm
                
                draw_footer(c, pagina + 1, total_paginas, usuario_exportador, len(estudiantes))
        
        c.save()
        buffer.seek(0)
        
        filename = f"reporte_{tipo}"
        if curso_id:
            filename += f"_curso{curso_id}"
        if asignatura_id:
            filename += f"_asignatura{asignatura_id}"
        filename += ".pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response
    
    except Exception as e:
        current_app.logger.error(f"Error al generar PDF académico: {e}", exc_info=True)
        flash('Error al generar el reporte: ' + str(e), 'danger')
        return redirect(url_for('academico.index'))