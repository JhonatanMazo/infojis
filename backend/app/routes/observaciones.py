import os
from flask import Blueprint, current_app, make_response, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from datetime import datetime
from io import BytesIO
from app import db
from app.models import Curso, Matricula, Observacion, Asignacion, User, Actividad
from app.services.configuracion_service import get_active_config
from app.utils.decorators import roles_required, admin_required
from app.utils.file_uploads import allowed_file, upload_documento
from app.forms.observacion import ObservacionForm, DummyDeleteForm
# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os

observaciones_bp = Blueprint('observacion', __name__, url_prefix='/observaciones')

@observaciones_bp.route('/', methods=['GET'])
@roles_required('admin', 'docente')
def listar_observaciones():
    curso_id = request.args.get('curso')
    tipo = request.args.get('tipo')

    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))

    anio_lectivo = active_config.get('anio')

    # Obtener cursos según el rol del usuario
    if current_user.is_admin():
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all()
    else:
        # Para docente: solo los cursos asignados en el año lectivo activo
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()

    query = Observacion.query.join(Matricula, Observacion.id_matricula == Matricula.id).filter(Matricula.año_lectivo == anio_lectivo, Observacion.eliminado == False)
    
    # Excluir observaciones de estudiantes que han sido transferidos
    query = query.filter(Matricula.estado != 'transferido')
    
    # Si es docente, filtrar solo las observaciones de sus cursos asignados
    if not current_user.is_admin():
        cursos_asignados_ids = [c.id for c in cursos]
        query = query.filter(Observacion.id_curso.in_(cursos_asignados_ids))

    if curso_id and curso_id != 'todos':
        query = query.filter(Observacion.id_curso == int(curso_id))
    if tipo and tipo != 'todos':
        query = query.filter(Observacion.tipo == tipo)

    page = request.args.get('page', 1, type=int)
    observaciones = query.order_by(Observacion.fecha.desc()).paginate(page=page, per_page=10)

    form = ObservacionForm()
    form_eliminar = DummyDeleteForm()
    form.curso.choices = [(c.id, c.nombre) for c in cursos]

    return render_template(
        'views/estudiantes/observaciones.html',
        observaciones=observaciones,
        cursos=cursos,
        form=form,
        form_eliminar=form_eliminar
    )


@observaciones_bp.route('/crear', methods=['POST'])
@roles_required('admin', 'docente')
def crear_observacion():
    try:
        id_matricula = int(request.form['id_matricula'])
        tipo = request.form.get('tipo')
        descripcion = request.form.get('descripcion', '').strip()
        fecha_str = request.form.get('fecha')
        detalles_filename = None

        if not fecha_str:
            raise ValueError('La fecha es requerida.')

        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede crear la observación.', 'danger')
            return redirect(url_for('observacion.listar_observaciones'))
        anio_lectivo = config['anio']

        if fecha.year != anio_lectivo:
            flash(f'La fecha de la observación ({fecha.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('observacion.listar_observaciones'))
        config = get_active_config()
        if not config:
            raise ValueError('No hay un año lectivo configurado como activo')
        anio_lectivo = config['anio']
        matricula = Matricula.query.filter_by(id=id_matricula, año_lectivo=anio_lectivo).first_or_404()

        # Verificar que el docente tiene acceso a este curso (si no es admin)
        if not current_user.is_admin():
            asignacion = Asignacion.query.filter_by(
                id_curso=matricula.id_curso,
                id_docente=current_user.id,
                estado='activo',
                anio_lectivo=anio_lectivo
            ).first()
            if not asignacion:
                raise ValueError("No tiene permisos para crear observaciones en este curso.")

        duplicado = Observacion.query.filter_by(
            id_matricula=matricula.id,
            id_curso=matricula.id_curso,
            tipo=tipo,
            fecha=fecha
        ).first()

        if duplicado:
            raise ValueError("Ya existe una observación de este tipo para este estudiante en este grado y fecha.")

        if 'detalles' in request.files:
            archivo = request.files['detalles']
            if archivo and allowed_file(archivo.filename):
                detalles_filename = upload_documento(archivo, f'observacion_{id_matricula}')

        nueva = Observacion(
            id_matricula=matricula.id,
            id_usuario=current_user.id,
            id_curso=matricula.id_curso,
            tipo=tipo,
            fecha=fecha,
            descripcion=descripcion,
            detalles=detalles_filename,
        )

        db.session.add(nueva)
        db.session.commit()

        # Crear notificaciones para los docentes relevantes
        try:
            # Encontrar todas las asignaciones activas para el curso de la matrícula
            asignaciones_del_curso = Asignacion.query.filter_by(
                id_curso=matricula.id_curso,
                estado='activo',
                anio_lectivo=anio_lectivo
            ).all()

            docentes_a_notificar = set()
            for asignacion in asignaciones_del_curso:
                # No crear una notificación para el usuario que crea la observación
                if asignacion.id_docente != current_user.id:
                    docentes_a_notificar.add(asignacion.id_docente)

            for docente_id in docentes_a_notificar:
                # Pick one asignacion for this docente
                asignacion = Asignacion.query.filter_by(
                    id_curso=matricula.id_curso,
                    id_docente=docente_id,
                    estado='activo',
                    anio_lectivo=anio_lectivo
                ).first()
                if asignacion:
                    actividad = Actividad(
                        tipo='observacion',
                        titulo=f'Nueva observación ({nueva.tipo})',
                        detalle=f'Se registró una observación para el estudiante {matricula.nombres} {matricula.apellidos} en el curso {matricula.curso.nombre}.',
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

            # Crear notificaciones para administradores
            try:
                admin_users = User.query.filter_by(rol='admin', estado='activo').all()
                for admin in admin_users:
                    actividad_admin = Actividad(
                        tipo='observacion',
                        titulo=f'Nueva observación ({nueva.tipo})',
                        detalle=f'Se registró una observación para el estudiante {matricula.nombres} {matricula.apellidos} en el curso {matricula.curso.nombre}.',
                        fecha=datetime.utcnow().date(),
                        creado_por=current_user.id,
                        id_asignacion=None
                    )
                    existing = Actividad.query.filter_by(
                        tipo=actividad_admin.tipo,
                        titulo=actividad_admin.titulo,
                        detalle=actividad_admin.detalle,
                        fecha=actividad_admin.fecha,
                        id_asignacion=actividad_admin.id_asignacion
                    ).first()
                    if not existing:
                        db.session.add(actividad_admin)
                db.session.commit()
            except Exception as admin_act_e:
                current_app.logger.error(f"Error creando actividad para admin en observación: {str(admin_act_e)}")
                # No relanzar la excepción para no impedir la creación de la observación

        except Exception as act_e:
            current_app.logger.error(f"Error creando actividad para observación: {str(act_e)}")
            # No relanzar la excepción para no impedir la creación de la observación

        flash('Observación creada con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear observación: {str(e)}', 'danger')

    return redirect(url_for('observacion.listar_observaciones'))


@observaciones_bp.route('/editar/<int:id>', methods=['POST'])
@roles_required('admin', 'docente')
def editar_observacion(id):
    try:
        observacion = Observacion.query.get_or_404(id)

        # Verificar que el docente tiene acceso a esta observación (si no es admin)
        if not current_user.is_admin():
            config = get_active_config()
            anio_lectivo = config['anio'] if config and 'anio' in config else None
            asignacion = Asignacion.query.filter_by(
                id_curso=observacion.id_curso,
                id_docente=current_user.id,
                estado='activo',
                anio_lectivo=anio_lectivo
            ).first()
            if not asignacion:
                raise ValueError("No tiene permisos para editar esta observación.")

        id_matricula = int(request.form['id_matricula'])
        tipo = request.form.get('tipo')
        descripcion = request.form.get('descripcion', '').strip()
        fecha_str = request.form.get('fecha')
        detalles_filename = observacion.detalles

        if not fecha_str:
            raise ValueError('La fecha es requerida.')

        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede editar la observación.', 'danger')
            return redirect(url_for('observacion.listar_observaciones'))
        anio_lectivo = config['anio']

        if fecha.year != anio_lectivo:
            flash(f'La fecha de la observación ({fecha.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('observacion.listar_observaciones'))
        config = get_active_config()
        if not config:
            raise ValueError('No hay un año lectivo configurado como activo')
        anio_lectivo = config['anio']
        matricula = Matricula.query.filter_by(id=id_matricula, año_lectivo=anio_lectivo).first_or_404()

        # Verificar que el docente tiene acceso al nuevo curso (si no es admin)
        if not current_user.is_admin() and matricula.id_curso != observacion.id_curso:
            asignacion = Asignacion.query.filter_by(
                id_curso=matricula.id_curso,
                id_docente=current_user.id,
                estado='activo',
                anio_lectivo=anio_lectivo
            ).first()
            if not asignacion:
                raise ValueError("No tiene permisos para mover la observación a este curso.")

        duplicado = Observacion.query.filter(
            Observacion.id != id,
            Observacion.id_matricula == id_matricula,
            Observacion.id_curso == matricula.id_curso,
            Observacion.tipo == tipo,
            Observacion.fecha == fecha
        ).first()

        if duplicado:
            raise ValueError("Ya existe otra observación de este tipo para este estudiante en esta fecha.")

        if 'detalles' in request.files:
            archivo = request.files['detalles']
            if archivo and allowed_file(archivo.filename):
                detalles_filename = upload_documento(archivo, f'observacion_{id_matricula}')

        observacion.id_matricula = id_matricula
        observacion.id_usuario = current_user.id
        observacion.id_curso = matricula.id_curso
        observacion.tipo = tipo
        observacion.fecha = fecha
        observacion.descripcion = descripcion
        observacion.detalles = detalles_filename

        db.session.commit()
        flash('Observación actualizada con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al editar observación: {str(e)}', 'danger')

    return redirect(url_for('observacion.listar_observaciones'))



@observaciones_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_observacion(id):
    form_eliminar = DummyDeleteForm()
    if not form_eliminar.validate_on_submit():
        flash('Token CSRF inválido.', 'danger')
        return redirect(url_for('observacion.listar_observaciones'))

    observacion = Observacion.query.get_or_404(id)
    try:
        observacion.eliminado = True
        observacion.eliminado_por = current_user.id
        observacion.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Observación enviada a la papelera de reciclaje.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar observación: {str(e)}', 'danger')

    return redirect(url_for('observacion.listar_observaciones'))




@observaciones_bp.route('/matriculas_por_curso/<int:id_curso>')
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


@observaciones_bp.route('/info_matricula/<int:id>')
@roles_required('admin', 'docente')
def info_matricula(id):
    m = Matricula.query.get_or_404(id)
    return jsonify({
        'curso_id': m.id_curso,
        'foto': url_for('static', filename=f'uploads/profiles/{m.foto}') if m.foto else '',
        'id': m.id
    })


@observaciones_bp.route('/exportar')
@roles_required('admin', 'docente')
def exportar_observaciones():
    try:
        data = request.form
        curso_id = request.args.get('curso')
        tipo = request.args.get('tipo')
        grado = data.get('grado')
        estado = data.get('estado')

        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else None

        query = Observacion.query.join(Matricula).join(Curso).filter(Observacion.eliminado == False)
        
        if anio_lectivo:
            query = query.filter(Matricula.año_lectivo == anio_lectivo)

        # Si es docente, filtrar solo las observaciones de sus cursos asignados
        if not current_user.is_admin():
            # Obtener cursos asignados al docente
            cursos = Curso.query.join(Asignacion).filter(
                Asignacion.id_docente == current_user.id,
                Asignacion.estado == 'activo',
                Asignacion.anio_lectivo == anio_lectivo
            ).distinct().all()
            cursos_asignados_ids = [c.id for c in cursos]
            query = query.filter(Observacion.id_curso.in_(cursos_asignados_ids))

        if curso_id and curso_id != 'todos':
            query = query.filter(Observacion.id_curso == int(curso_id))
        if tipo and tipo != 'todos':
            query = query.filter(Observacion.tipo == tipo)
        if grado and grado != 'todos':
            query = query.filter(Matricula.id_curso == int(grado))
        if estado and estado != 'todos':
            query = query.filter(Matricula.estado == estado)
            
        if not query.first():
            flash('No hay observaciones para exportar', 'warning')
            return redirect(url_for('observacion.listar_observaciones'))

        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        observaciones = query.order_by(Observacion.fecha.desc()).all()
        

        # Crear PDF con diseño premium
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar márgenes
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        
        # Colores premium
        color_primary = HexColor("#2C3E50")
        color_black = HexColor("#000000")
        color_white = HexColor("#FFFFFF")
        
        # Calcular cuántas observaciones caben por página (20 por página)
        observaciones_por_pagina = 20
        total_paginas = (len(observaciones) + observaciones_por_pagina - 1) // observaciones_por_pagina
        
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
            c.setFillColor(color_black)
            c.drawCentredString(width/2, height-20*mm, "JARDÍN INFANTIL SONRISAS")
            
            c.setFont("Helvetica-Oblique", 10)
            c.setFillColor(color_black)
            c.drawCentredString(width/2, height-25*mm, '"Aprendiendo y sonriendo"')
            
            c.setFont("Helvetica", 9)
            c.setFillColor(color_black)
            c.drawCentredString(width/2, height-30*mm, "Código DANE N° 320001800766")
            c.drawCentredString(width/2, height-35*mm, "Teléfono: 300 149 8933")
            
            # Título del reporte
            c.setFont("Helvetica-Bold", 20)
            c.setFillColor(color_black)
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE OBSERVACIONES")
            
            # Información de filtros aplicados
            filtros_texto = []
            if curso_id and curso_id != 'todos':
                curso = Curso.query.get(int(curso_id))
                if curso:
                    filtros_texto.append(f"Curso: {curso.nombre}")
            if tipo and tipo != 'todos':
                filtros_texto.append(f"Tipo: {tipo.capitalize()}")
                
            if filtros_texto:
                c.setFont("Helvetica", 10)
                c.setFillColor(HexColor("#666666"))
                c.drawCentredString(width/2, height-58*mm, f"Filtros aplicados: {', '.join(filtros_texto)}")
            
            # Ajustar posición inicial de la tabla
            current_y = height - 65*mm
            
            # Fondo negro para el encabezado de la tabla
            header_height = 8*mm
            c.setFillColor(color_black)
            c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
            
            # Calcular posiciones centradas para las columnas 
            available_width = width - (2 * margin_left)
            column_width = available_width / 7  # 7 columnas
            
            # Definir posiciones de las columnas centradas
            col_positions = [
                margin_left + (i * column_width) for i in range(7)
            ]
            
            # Encabezados de la tabla en blanco sobre fondo negro
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(color_white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "ESTUDIANTE", "CURSO", "TIPO", "FECHA", "DESCRIPCIÓN", "REGISTRADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener observaciones para esta página
            inicio = pagina * observaciones_por_pagina
            fin = inicio + observaciones_por_pagina
            observaciones_pagina = observaciones[inicio:fin]
            
            for i, observacion in enumerate(observaciones_pagina, inicio + 1):
                # Obtener el nombre del usuario que registró la observación (solo primer nombre y apellido)
                if observacion.usuario:
                    # Obtener primer nombre y primer apellido
                    nombres = observacion.usuario.nombre.split()
                    apellidos = observacion.usuario.apellidos.split() if observacion.usuario.apellidos else []
                    primer_nombre = nombres[0] if nombres else ""
                    primer_apellido = apellidos[0] if apellidos else ""
                    registrado_por = f"{primer_nombre} {primer_apellido}"
                else:
                    registrado_por = "N/A"
                
                # Preparar datos para cada columna
                datos = [
                    str(i),
                    f"{observacion.matricula.nombres} {observacion.matricula.apellidos}"[:12] + '...' if len(f"{observacion.matricula.nombres} {observacion.matricula.apellidos}") > 15 else f"{observacion.matricula.nombres} {observacion.matricula.apellidos}",
                    observacion.matricula.curso.nombre[:8] + '...' if len(observacion.matricula.curso.nombre) > 11 else observacion.matricula.curso.nombre,
                    observacion.tipo[:10] + '...' if len(observacion.tipo) > 15 else observacion.tipo,
                    observacion.fecha.strftime('%d/%m/%Y'),
                    observacion.descripcion[:20] + '...' if len(observacion.descripcion) > 25 else observacion.descripcion,
                    registrado_por[:10] + '...' if len(registrado_por) > 13 else registrado_por
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(color_black)
                for j, dato in enumerate(datos):
                    c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(observaciones)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)

        filename = "reporte_observaciones"
        if curso_id and curso_id != 'todos':
            curso = Curso.query.get(int(curso_id))
            if curso:
                filename += f"_{curso.nombre.lower().replace(' ', '_')}"
        if tipo and tipo != 'todos':
            filename += f"_{tipo.lower()}"
        filename += ".pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response
    
    except Exception as e:
            current_app.logger.error(f"Error al generar PDF de observacion: {e}", exc_info=True)
            flash('Error al generar el reporte PDF: '+str(e),'danger')
            return redirect(url_for('observacion.listar_observaciones'))