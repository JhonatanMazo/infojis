from flask import Blueprint, current_app, make_response, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from datetime import datetime
from app import db
from app.models import Curso, Matricula, Actividad, Asignacion
from app.utils.decorators import admin_required
from app.utils.file_uploads import upload_profile_picture, remove_profile_picture, allowed_file
from io import BytesIO
from app.forms.filtros import FiltroMatriculaForm
from app.services.configuracion_service import get_active_config
from app.services.matricula_service import clear_matriculas_cache

# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os

matricula_bp = Blueprint('matricula', __name__, url_prefix='/matriculas')


@matricula_bp.route('/', methods=['GET', 'POST'])
@admin_required
def listar_matricula():
    """Lista todas las matrículas del año lectivo activo con paginación"""
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']
    form = FiltroMatriculaForm()

    # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
    cursos_ids = db.session.query(Asignacion.id_curso).filter(
        Asignacion.anio_lectivo == anio_lectivo,
        Asignacion.estado == 'activo'
    ).distinct().all()
    cursos_ids = [c[0] for c in cursos_ids]
    cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []

    # Añadir 'transferido' a las opciones del filtro de estado
    form.estado.choices = [('', 'Todos'), ('activo', 'Activo'), ('retirado', 'Retirado'), ('transferido', 'Transferido')]


    form.curso.choices = [(0, 'Todos')] + [(curso.id, curso.nombre) for curso in cursos]

    if form.validate_on_submit():
        estado = form.estado.data
        curso = form.curso.data if form.curso.data != 0 else None
        return redirect(url_for('matricula.listar_matricula', estado=estado, curso=curso))

    page = request.args.get('page', 1, type=int)
    per_page = 10
    estado = request.args.get('estado', '')
    curso = request.args.get('curso', type=int)

    if request.method == 'GET':
        form.estado.data = estado
        form.curso.data = int(curso) if curso else 0

    query = Matricula.query.filter_by(año_lectivo=anio_lectivo, eliminado=False).order_by(Matricula.apellidos, Matricula.nombres)

    if estado:
        query = query.filter_by(estado=estado)
    if curso:
        query = query.filter_by(id_curso=curso)

    matriculas = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('views/estudiantes/matriculas.html',
                       form=form,
                       cursos=cursos,
                       anio_lectivo=anio_lectivo,
                       active_config=active_config,
                       Matricula=Matricula,
                       matriculas=matriculas,
                       datetime=datetime)


@matricula_bp.route('/crear', methods=['POST'])
@admin_required
def crear_matricula():
    try:
        active_config = get_active_config()
        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('matricula.listar_matricula'))

        id_curso = int(request.form['id_curso'])
        curso = Curso.query.get(id_curso)
        if not curso or curso.estado != 'activo':
            flash('Curso no disponible', 'danger')
            return redirect(url_for('matricula.listar_matricula'))

        documento = request.form['documento']
        email = request.form['email']
        # Se elimina la validación de email duplicado para permitir el mismo correo en varias matrículas.
        existente = Matricula.query.filter(
            Matricula.documento == documento
        ).first()
        if existente:
            flash('Ya existe un estudiante registrado con ese documento', 'danger')
            return redirect(url_for('matricula.listar_matricula'))

        fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
        fecha_matricula = datetime.strptime(request.form['fecha_matricula'], '%Y-%m-%d').date()

        filename = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename.strip() != '':
                filename = upload_profile_picture(file, documento)

        nueva_matricula = Matricula(
            nombres=request.form['nombres'],
            apellidos=request.form['apellidos'],
            genero=request.form['genero'],
            documento=documento,
            email=email,
            telefono=request.form['telefono'],
            direccion=request.form['direccion'],
            fecha_nacimiento=fecha_nacimiento,
            id_curso=id_curso,
            año_lectivo=active_config['anio'],
            estado=request.form['estado'],
            fecha_matricula=fecha_matricula,
            foto=filename
        )

        db.session.add(nueva_matricula)
        db.session.commit()
        
        # Notificar a los docentes del curso
        try:
            asignaciones_del_curso = Asignacion.query.filter_by(
                id_curso=nueva_matricula.id_curso,
                estado='activo',
                anio_lectivo=active_config['anio']
            ).all()

            docentes_a_notificar = set()
            for asignacion in asignaciones_del_curso:
                # No notificar al admin que crea la matrícula si también es docente de ese curso
                if asignacion.id_docente != current_user.id:
                    docentes_a_notificar.add(asignacion.id_docente)

            for docente_id in docentes_a_notificar:
                # Pick one asignacion for this docente
                asignacion = Asignacion.query.filter_by(
                    id_curso=nueva_matricula.id_curso,
                    id_docente=docente_id,
                    estado='activo',
                    anio_lectivo=active_config['anio']
                ).first()
                if asignacion:
                    actividad = Actividad(
                        tipo='matricula',
                        titulo='Nueva matrícula registrada',
                        detalle=f'Se ha matriculado al estudiante {nueva_matricula.nombres} {nueva_matricula.apellidos} en el curso {nueva_matricula.curso.nombre}.',
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
            current_app.logger.error(f"Error creando actividad para matrícula: {str(act_e)}")

        clear_matriculas_cache()
        flash('Matrícula creada correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creando matrícula: {str(e)}")
        flash('Error al crear matrícula: ' + str(e), 'danger')

    return redirect(url_for('matricula.listar_matricula'))


@matricula_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_matricula(id):
    """Edita una matrícula existente con validaciones mejoradas"""
    matricula = Matricula.query.get_or_404(id)
    
    try:
        active_config = get_active_config()
        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('matricula.listar_matricula'))
            
        if matricula.año_lectivo != active_config['anio']:
            flash(f'Solo puedes editar matrículas del año lectivo activo ({active_config["anio"]})', 'danger')
            return redirect(url_for('matricula.listar_matricula'))

        # Obtener datos del formulario
        documento = request.form['documento'].strip()
        email = request.form['email'].strip().lower()
        nuevo_curso_id = int(request.form['id_curso'])

        # ✅ Validación de duplicados mejorada (solo mismo año lectivo)
        documento_duplicado = Matricula.query.filter(
            Matricula.documento == documento,
            Matricula.id != id,
            Matricula.año_lectivo == active_config['anio']
        ).first()
        
        if documento_duplicado:
            flash('Ya existe otro estudiante con ese documento en el año lectivo actual', 'danger')
            return redirect(url_for('matricula.listar_matricula'))


        # ✅ Validación de cambio de curso y cupo
        if matricula.id_curso != nuevo_curso_id:
            curso_nuevo = Curso.query.get(nuevo_curso_id)
            if not curso_nuevo or curso_nuevo.estado != 'activo':
                flash('El curso seleccionado no está disponible', 'danger')
                return redirect(url_for('matricula.listar_matricula'))

        # ✅ Actualizar datos de la matrícula
        matricula.nombres = request.form['nombres'].strip()
        matricula.apellidos = request.form['apellidos'].strip()
        matricula.genero = request.form['genero']
        matricula.documento = documento
        matricula.email = email
        matricula.telefono = request.form['telefono'].strip()
        matricula.direccion = request.form['direccion'].strip()
        matricula.id_curso = nuevo_curso_id
        matricula.estado = request.form['estado']
        
        # ✅ Convertir y validar fechas
        try:
            matricula.fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
            matricula.fecha_matricula = datetime.strptime(request.form['fecha_matricula'], '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido', 'danger')
            return redirect(url_for('matricula.listar_matricula'))

        # ✅ Manejo de la foto de perfil
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename.strip() != '' and allowed_file(file.filename):
                # Eliminar foto anterior si existe
                if matricula.foto:
                    remove_profile_picture(matricula.foto)
                
                # Subir nueva foto
                filename = upload_profile_picture(file, documento)
                matricula.foto = filename

        # ✅ Guardar cambios en la base de datos
        db.session.commit()
        clear_matriculas_cache()
        
        flash('Matrícula actualizada correctamente', 'success')
        
    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f"Error de valor al editar matrícula {id}: {str(e)}")
        flash('Error en los datos proporcionados: ' + str(e), 'danger')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error inesperado al editar matrícula {id}: {str(e)}")
        flash('Error al actualizar matrícula: ' + str(e), 'danger')
    
    return redirect(url_for('matricula.listar_matricula'))


@matricula_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_matricula(id):
    matricula = Matricula.query.get_or_404(id)
    
    if matricula.estado == 'activo': 
        flash('No se puede eliminar un estudiante activo. Por favor, desactívelo primero desde el formulario de edición.', 'danger')
        return redirect(url_for('matricula.listar_matricula'))
    
    
    try:
        matricula.eliminado = True
        matricula.eliminado_por = current_user.id
        matricula.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        clear_matriculas_cache()
        flash('Matrícula enviada a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error eliminando matrícula {id}: {str(e)}")
        flash('Error al eliminar la matrícula', 'danger')
    
    return redirect(url_for('matricula.listar_matricula'))


@matricula_bp.route('/actualizar-por-cambio-curso', methods=['POST'])
@admin_required
def actualizar_por_cambio_curso():
    """Maneja cambios masivos cuando se desactiva un curso"""
    try:
        active_config = get_active_config()
        if not active_config:
            return jsonify({'success': False, 'error': 'No hay año activo'}), 400

        data = request.get_json()
        curso_id = data.get('curso_id')
        nuevo_estado = data.get('nuevo_estado')

        if not curso_id or nuevo_estado not in ['activo', 'inactivo']:
            return jsonify({'success': False, 'error': 'Datos inválidos'}), 400

        if nuevo_estado == 'inactivo':
            Matricula.query.filter_by(
                id_curso=curso_id,
                año_lectivo=active_config['anio'],
                estado='activo'
            ).update({'estado': 'retirado'})
            
            db.session.commit()
            clear_matriculas_cache()
            
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error actualizando por cambio de curso: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
    
    
    
@matricula_bp.route('/exportar', methods=['GET'])
@admin_required
def exportar_matricula():
    """Exporta matrículas a PDF con diseño premium y 20 registros por página"""
    try:
        active_config = get_active_config()
        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('matricula.listar_matricula'))

        # Obtener parámetros de filtrado
        estado = request.args.get('estado', '')
        curso_id = request.args.get('curso', type=int)
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()
        
        # Consulta de matrículas
        query = Matricula.query.filter_by(año_lectivo=active_config['anio'])
        
        if estado:
            query = query.filter_by(estado=estado)
        if curso_id:
            query = query.filter_by(id_curso=curso_id)
            
        matriculas = query.order_by(Matricula.apellidos, Matricula.nombres).all()

        if not matriculas:
            flash('No hay matrículas para exportar con los filtros actuales', 'warning')
            return redirect(url_for('matricula.listar_matricula'))

        # Crear PDF con diseño premium
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar márgenes
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        
        # Colores premium
        color_primary = HexColor("#2C3E50")
        color_active = HexColor("#27AE60")
        color_inactive = HexColor("#E74C3C")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        # Calcular cuántas matrículas caben por página (20 por página)
        matriculas_por_pagina = 20
        total_paginas = (len(matriculas) + matriculas_por_pagina - 1) // matriculas_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE MATRÍCULAS")
            
            # Información de año lectivo y filtros aplicados
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, height-58*mm, f"Año lectivo: {active_config['anio']}")
            
            filtros_texto = []
            if estado:
                filtros_texto.append(f"Estado: {estado}")
            if curso_id:
                curso = Curso.query.get(curso_id)
                filtros_texto.append(f"Curso: {curso.nombre}")
                
            if filtros_texto:
                c.drawCentredString(width/2, height-63*mm, f"Filtros aplicados: {', '.join(filtros_texto)}")
            
            # Ajustar posición inicial de la tabla
            current_y = height - 70*mm
            
            # Fondo negro para el encabezado de la tabla
            header_height = 8*mm
            c.setFillColor(black)
            c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
            
            # Calcular posiciones centradas para las columnas (7 columnas para matrículas)
            available_width = width - (2 * margin_left)
            column_width = available_width / 7  # 7 columnas
            
            # Definir posiciones de las columnas centradas
            col_positions = [
                margin_left + (i * column_width) for i in range(7)
            ]
            
            # Encabezados de la tabla en blanco sobre fondo negro
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "NOMBRES", "APELLIDOS", "DOCUMENTO", "CURSO", "F. MATRÍCULA", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener matrículas para esta página
            inicio = pagina * matriculas_por_pagina
            fin = inicio + matriculas_por_pagina
            matriculas_pagina = matriculas[inicio:fin]
            
            for i, matricula in enumerate(matriculas_pagina, inicio + 1):
                # Preparar datos para cada columna
                datos = [
                    str(i),
                    matricula.nombres[:12] + '...' if len(matricula.nombres) > 15 else matricula.nombres,
                    matricula.apellidos[:12] + '...' if len(matricula.apellidos) > 15 else matricula.apellidos,
                    matricula.documento[:10] + '...' if len(matricula.documento) > 13 else matricula.documento,
                    matricula.curso.nombre[:10] + '...' if len(matricula.curso.nombre) > 13 else matricula.curso.nombre,
                    matricula.fecha_matricula.strftime('%d/%m/%Y'),
                    matricula.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 6:  # Columna de estado
                        if matricula.estado.lower() == 'activo':
                            c.setFillColor(color_active)
                        else:
                            c.setFillColor(color_inactive)
                    
                    c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                    c.setFillColor(black)  # Restablecer color para las siguientes columnas
                
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(matriculas)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        # Guardar el PDF
        c.save()
        buffer.seek(0)
        
        filename = f"reporte_matriculas"
        if estado:
            filename += f"_{estado}"
        if curso_id:
            filename += f"_curso{curso_id}"
        filename += ".pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de matrículas: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('matricula.listar_matricula'))