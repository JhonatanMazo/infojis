from flask import Blueprint, current_app, make_response, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.services.configuracion_service import get_active_config
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from app import db
from app.models import Curso, Matricula, Inclusion, Asignacion
from app.forms.inclusion import FiltroInclusion
from app.utils.decorators import admin_required, roles_required
from app.utils.file_uploads import allowed_file, upload_documento, remove_documento
# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os


inclusion_bp = Blueprint('inclusion', __name__, url_prefix='/inclusion')

@inclusion_bp.route('/', methods=['GET'])
@roles_required('admin', 'docente')
def listar_inclusiones():
    form = FiltroInclusion()
    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None

    # Obtener cursos según el rol del usuario
    if current_user.is_admin():
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []
    else:
        # Para docente: solo los cursos asignados en el año lectivo activo
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()

    form.curso.choices = [('', 'Todos')] + [(str(c.id), c.nombre) for c in cursos]

    query = Inclusion.query.filter_by(eliminado=False)
    if anio_lectivo:
        # Solo inclusiones de matrículas del año lectivo actual
        query = query.join(Matricula).filter(Matricula.año_lectivo == anio_lectivo)
        
    # Excluir registros de estudiantes que han sido transferidos
    query = query.filter(Matricula.estado != 'transferido')
    
    # Si es docente, filtrar solo las inclusiones de sus cursos asignados
    if not current_user.is_admin():
        cursos_asignados_ids = [c.id for c in cursos]
        query = query.filter(Inclusion.id_curso.in_(cursos_asignados_ids))
    
    if form.validate_on_submit() or request.args:
        curso_id = request.args.get('curso')
        if curso_id:
            query = query.filter(Inclusion.id_curso == int(curso_id))

    page = request.args.get('page', 1, type=int)
    inclusiones = query.order_by(Inclusion.fecha_ingreso.desc()).paginate(page=page, per_page=10)
    matriculas = Matricula.query.filter_by(estado='activo').filter(Matricula.año_lectivo == anio_lectivo).all() if anio_lectivo else []
    
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']

    return render_template(
        'views/inclusion.html',
        inclusiones=inclusiones,
        cursos=cursos,
        matriculas=matriculas,
        form=form
    )

@inclusion_bp.route('/crear', methods=['POST'])
@admin_required
def crear_inclusion():
    
    try:
        id_matricula = int(request.form['id_matricula'])
        id_curso = int(request.form['id_curso'])
        tipo_necesidad = request.form['tipo_necesidad']
        plan_apollo = request.form.get('plan_apollo', '')
        fecha_ingreso_str = request.form.get('fecha_ingreso')
        detalles_filename = None

        if not fecha_ingreso_str:
            raise ValueError('La fecha de ingreso es requerida.')
        fecha_ingreso = datetime.strptime(fecha_ingreso_str, '%Y-%m-%d').date()

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede crear el registro de inclusión.', 'danger')
            return redirect(url_for('inclusion.listar_inclusiones'))
        anio_lectivo = config['anio']

        if fecha_ingreso.year != anio_lectivo:
            flash(f'La fecha de ingreso ({fecha_ingreso.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('inclusion.listar_inclusiones'))

        # Subir documento de detalles (si se envía)
        if 'detalles' in request.files:
            file_detalles = request.files['detalles']
            if file_detalles and allowed_file(file_detalles.filename):
                detalles_filename = upload_documento(file_detalles, f'inclusion_detalles_{id_matricula}')

        inclusion = Inclusion(
            id_matricula=id_matricula,
            id_curso=id_curso,
            tipo_necesidad=tipo_necesidad,
            plan_apollo=plan_apollo,
            fecha_ingreso=fecha_ingreso,
            detalles=detalles_filename,
            id_usuario=current_user.id
        )

        db.session.add(inclusion)
        db.session.commit()
        
        # Notificar a los docentes del curso
        try:
            from app.models import Actividad
            config = get_active_config()
            if config and 'anio' in config:
                anio_lectivo = config['anio']
                asignaciones_del_curso = Asignacion.query.filter_by(
                    id_curso=inclusion.id_curso,
                    estado='activo',
                    anio_lectivo=anio_lectivo
                ).all()

                docentes_a_notificar = set()
                for asignacion in asignaciones_del_curso:
                    if asignacion.id_docente != current_user.id:
                        docentes_a_notificar.add(asignacion.id_docente)

                for docente_id in docentes_a_notificar:
                    # Pick one asignacion for this docente
                    asignacion = Asignacion.query.filter_by(
                        id_curso=inclusion.id_curso,
                        id_docente=docente_id,
                        estado='activo',
                        anio_lectivo=anio_lectivo
                    ).first()
                    if asignacion:
                        actividad = Actividad(
                            tipo='inclusion',
                            titulo='Nuevo registro de inclusión',
                            detalle=f'Se creó un registro de inclusión para el estudiante {inclusion.matricula.nombres} {inclusion.matricula.apellidos} en el curso {inclusion.matricula.curso.nombre}.',
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
        except Exception as act_e:
            current_app.logger.error(f"Error creando actividad para inclusión: {str(act_e)}")

        flash('Inclusión registrada correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear inclusión: {str(e)}', 'danger')

    return redirect(url_for('inclusion.listar_inclusiones'))

@inclusion_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_inclusion(id):
    inclusion = Inclusion.query.get_or_404(id)
    try:
        id_matricula = int(request.form['id_matricula'])
        inclusion.id_matricula = id_matricula
        inclusion.id_curso = int(request.form['id_curso'])
        inclusion.tipo_necesidad = request.form['tipo_necesidad']
        inclusion.plan_apollo = request.form.get('plan_apollo', '')
        fecha_ingreso_str = request.form.get('fecha_ingreso')

        if not fecha_ingreso_str:
            raise ValueError('La fecha de ingreso es requerida.')
        inclusion.fecha_ingreso = datetime.strptime(fecha_ingreso_str, '%Y-%m-%d').date()

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede editar el registro de inclusión.', 'danger')
            return redirect(url_for('inclusion.listar_inclusiones'))
        anio_lectivo = config['anio']

        if inclusion.fecha_ingreso.year != anio_lectivo:
            flash(f'La fecha de ingreso ({inclusion.fecha_ingreso.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('inclusion.listar_inclusiones'))

        # Reemplazar documento de detalles si se sube uno nuevo
        if 'detalles' in request.files:
            doc = request.files['detalles']
            if doc and allowed_file(doc.filename):
                if inclusion.detalles:
                    remove_documento(inclusion.detalles)
                inclusion.detalles = upload_documento(doc, f'inclusion_detalles_{id_matricula}')

        db.session.commit()
        flash('Inclusión actualizada correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al editar inclusión: {str(e)}', 'danger')

    return redirect(url_for('inclusion.listar_inclusiones'))

@inclusion_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_inclusion(id):
    inclusion = Inclusion.query.get_or_404(id)
    try:
        inclusion.eliminado = True
        inclusion.eliminado_por = current_user.id
        inclusion.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Inclusión enviada a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar inclusión: {str(e)}', 'danger')
    return redirect(url_for('inclusion.listar_inclusiones'))

@inclusion_bp.route('/exportar', methods=['GET'])
@roles_required('admin', 'docente')
def exportar_inclusiones():
    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    
    curso_id = request.args.get('curso')
    query = Inclusion.query.filter_by(eliminado=False)
    
    if anio_lectivo:
        query = query.join(Matricula).filter(Matricula.año_lectivo == anio_lectivo)
    
    # Si es docente, filtrar solo las inclusiones de sus cursos asignados
    if not current_user.is_admin():
        # Obtener cursos asignados al docente
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()
        cursos_asignados_ids = [c.id for c in cursos]
        query = query.filter(Inclusion.id_curso.in_(cursos_asignados_ids))
    
    if curso_id:
        query = query.filter(Inclusion.id_curso == int(curso_id))
        
    inclusiones = query.order_by(Inclusion.fecha_ingreso.desc()).all()
    
    if not inclusiones:
        flash('No hay inclusiones para exportar', 'warning')
        return redirect(url_for('inclusion.listar_inclusiones'))
    

    # Obtener primer nombre y primer apellido del usuario actual
    nombres = current_user.nombre.split()
    apellidos = current_user.apellidos.split() if current_user.apellidos else []
    
    primer_nombre = nombres[0] if nombres else ""
    primer_apellido = apellidos[0] if apellidos else ""
    
    usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

    # Crear PDF con diseño premium similar al de cursos
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Configurar márgenes
    margin_left = 10 * mm
    margin_right = width - (10 * mm)
    margin_top = height - (15 * mm)
    
    # Colores premium
    color_primary = HexColor("#2C3E50")
    black = HexColor("#000000")
    white = HexColor("#FFFFFF")
    
    # Calcular cuántas inclusiones caben por página
    inclusiones_por_pagina = 20
    total_paginas = (len(inclusiones) + inclusiones_por_pagina - 1) // inclusiones_por_pagina
    
    for pagina in range(total_paginas):
        if pagina > 0:
            c.showPage()
        
        # Fondo con textura sutil
        c.setFillColor(HexColor("#FBFCFC"))
        c.rect(0, 0, width, height, fill=1, stroke=0)
        
        # Marco decorativo
        c.setStrokeColor(color_primary)
        c.setLineWidth(0.5)
        c.roundRect(10*mm, 10*mm, width-20*mm, height-20*mm, 5*mm, stroke=1, fill=0)
        
        # Encabezado con logo
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            logo_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
            
            if os.path.exists(logo_path):
                c.drawImage(logo_path, margin_left, height-50*mm, width=35*mm, height=40*mm, 
                           mask='auto', preserveAspectRatio=True)
            else:
                c.setFont("Helvetica-Bold", 16)
                c.setFillColor(color_primary)
                c.drawString(margin_left, height-30*mm, "JARDÍN INFANTIL")
                c.drawString(margin_left, height-35*mm, "SONRISAS")
        except Exception as e:
            print(f"Error al cargar el logo: {str(e)}")
        
        # Encabezado con información institucional
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
        
        # Título del reporte
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(black)
        c.drawCentredString(width/2, height-50*mm, "REPORTE DE INCLUSIONES")
        
        # Información de filtros aplicados
        info_text = []
        if curso_id:
            curso_nombre = Curso.query.get(int(curso_id)).nombre if curso_id else ''
            info_text.append(f"Curso: {curso_nombre}")
        
            
        if info_text:
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, height-58*mm, " | ".join(info_text))
        
        # Ajustar posición inicial de la tabla
        current_y = height - 65*mm  
        
        # Fondo negro para el encabezado de la tabla
        header_height = 8*mm 
        c.setFillColor(black)
        c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
        
        # Calcular posiciones centradas para las columnas
        available_width = width - (2 * margin_left)
        column_width = available_width / 6  # 6 columnas
        
        # Definir posiciones de las columnas centradas
        col_positions = [
            margin_left + (i * column_width) for i in range(6)
        ]
        
        # Encabezados de la tabla en blanco sobre fondo negro
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(white)
        
        # Dibujar encabezados centrados en cada columna
        headers = ["N°", "ESTUDIANTE", "DOCUMENTO", "CURSO", "NECESIDAD", "FECHA INGRESO"]
        for i, header in enumerate(headers):
            c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)  
        
        current_y -= 15*mm
        
        # Contenido de la tabla
        c.setFont("Helvetica", 8)
        
        # Obtener inclusiones para esta página
        inicio = pagina * inclusiones_por_pagina
        fin = inicio + inclusiones_por_pagina
        inclusiones_pagina = inclusiones[inicio:fin]
        
        for i, inclusion in enumerate(inclusiones_pagina, inicio + 1):
            # Preparar datos para cada columna
            estudiante_nombre = f"{inclusion.matricula.nombres} {inclusion.matricula.apellidos}" if inclusion.matricula else "N/A"
            documento = inclusion.matricula.documento if inclusion.matricula and inclusion.matricula.documento else "N/A"
            curso_nombre = inclusion.curso.nombre if inclusion.curso else "N/A"
            necesidad = inclusion.tipo_necesidad[:20] + '...' if inclusion.tipo_necesidad and len(inclusion.tipo_necesidad) > 23 else (inclusion.tipo_necesidad or "N/A")
            fecha_ingreso = inclusion.fecha_ingreso.strftime('%d/%m/%Y') if inclusion.fecha_ingreso else "N/A"
            
            datos = [
                str(i),
                estudiante_nombre[:25],
                documento[:15],
                curso_nombre[:20],
                necesidad,
                fecha_ingreso
            ]
            
            # Dibujar datos centrados en cada columna
            c.setFillColor(black)
            for j, dato in enumerate(datos):
                c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato[:30])
            
            current_y -= 5*mm  
            
            # Línea separadora tenue
            c.setStrokeColor(HexColor("#DDDDDD"))
            c.setLineWidth(0.2)
            c.line(margin_left, current_y, margin_right, current_y)
            
            current_y -= 4*mm  
        
        # Pie de página en cada hoja
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(HexColor("#777777"))
        c.drawCentredString(width/2, 25*mm, f"Reporte generado por {usuario_exportador} - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(inclusiones)}")
        c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
    
    c.save()
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f"attachment; filename=reporte_inclusiones.pdf"
    return response

@inclusion_bp.route('/matriculas_por_curso/<int:id_curso>')
@roles_required('admin', 'docente')
def matriculas_por_curso(id_curso):
    # Verificar que el docente tiene acceso a este curso
    if not current_user.is_admin():
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else None
        
        asignacion = Asignacion.query.filter_by(
            id_curso=id_curso,
            id_docente=current_user.id,
            estado='activo',
            anio_lectivo=anio_lectivo
        ).first()
        
        if not asignacion:
            return jsonify([])  # No tiene acceso, devolver lista vacía
    
    # Excluir estudiantes transferidos del selector
    matriculas = Matricula.query.filter(
        Matricula.id_curso == id_curso,
        Matricula.estado != 'transferido'
    ).all()
    data = []
    for m in matriculas:
        data.append({
            'id': m.id,
            'nombre': f"{m.nombres} {m.apellidos}",
            'foto': url_for('static', filename=f'uploads/profiles/{m.foto}') if m.foto else ''
        })
    return jsonify(data)


@inclusion_bp.route('/info_matricula/<int:id>')
@roles_required('admin', 'docente')
def info_matricula(id):
    m = Matricula.query.get_or_404(id)
    return jsonify({
        'curso_id': m.id_curso,
        'foto': url_for('static', filename=f'uploads/profiles/{m.foto}') if m.foto else '',
        'id': m.id
    })