from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, make_response
from flask_login import current_user
from app import db
from app.models import Asignacion, User, Curso, Asignatura, Actividad, Matricula
from io import BytesIO
from app.utils.decorators import admin_required, roles_required
from datetime import datetime
from app.services.configuracion_service import get_active_config
from app.services.asignacion_service import clear_asignaciones_cache

# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os


asignacion_bp = Blueprint('asignacion', __name__, url_prefix='/asignacion')


@asignacion_bp.route('/')
@roles_required('admin', 'docente')
def index():
    page = request.args.get('page', 1, type=int)
    curso_id = request.args.get('curso_id', type=int)

    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))

    anio_lectivo = active_config['anio']

    # Siempre obtener datos frescos, no usar caché para evitar problemas de visualización
    # Construir la consulta desde cero
    asignaciones_query = Asignacion.query.filter_by(anio_lectivo=anio_lectivo, eliminado=False)

    if curso_id:
        asignaciones_query = asignaciones_query.filter_by(id_curso=curso_id)

    if current_user.rol == 'docente':
        asignaciones_query = asignaciones_query.filter_by(id_docente=current_user.id)

    asignaciones = asignaciones_query.order_by(
        Asignacion.fecha_asignacion.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    # Obtener datos para formularios
    docentes = User.query.filter_by(rol='docente', estado='activo').order_by(User.apellidos).all()
    asignaturas = Asignatura.query.filter_by(estado='activo').order_by(Asignatura.nombre).all()
    # Para los modales de creación/edición, necesitamos TODOS los cursos activos.
    cursos = Curso.query.filter_by(estado='activo').order_by(Curso.nombre).all()

    # Para el filtro de la tabla, ahora mostraremos todos los cursos activos.
    cursos_filtro = Curso.query.filter_by(estado='activo').order_by(Curso.nombre).all()

    # Rango visual de registros
    start_index = (asignaciones.page - 1) * asignaciones.per_page + 1
    end_index = min(start_index + asignaciones.per_page - 1, asignaciones.total)
    

    return render_template(
        'views/asignacion.html',
        asignaciones=asignaciones,
        docentes=docentes,
        cursos=cursos_filtro, # Usamos la lista filtrada para el dropdown de la tabla
        asignaturas=asignaturas,
        curso_filtrado=curso_id,
        start_index=start_index,
        end_index=end_index,
        anio_lectivo=anio_lectivo,
        active_config=active_config
    )
    # NOTA: El modal de creación/edición usará la variable 'cursos' que se pasa implícitamente al renderizar.


@asignacion_bp.route('/crear', methods=['POST'])
@admin_required
def crear():
    try:
        active_config = get_active_config()
        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('asignacion.index'))

        # Validar y obtener datos del formulario
        id_docente = int(request.form['select-docente'])
        id_asignatura = int(request.form['select-asignatura'])
        id_curso = int(request.form['select-curso'])
        horas_impartidas = request.form.get('horas-impartidas', type=int)
        observaciones = request.form.get('observaciones', '')

        # Validar que todos los elementos estén activos
        docente = User.query.filter_by(id=id_docente, rol='docente', estado='activo').first()
        if not docente:
            flash('El docente seleccionado no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        asignatura = Asignatura.query.filter_by(id=id_asignatura, estado='activo').first()
        if not asignatura:
            flash('La asignatura seleccionada no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        curso = Curso.query.filter_by(id=id_curso, estado='activo').first()
        if not curso:
            flash('El curso seleccionado no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        # Verificar asignación existente
        if Asignacion.query.filter_by(
            id_curso=id_curso,
            id_asignatura=id_asignatura,
            anio_lectivo=active_config['anio'],
            estado='activo'
        ).first():
            flash('Ya existe una asignación activa para esta combinación en el año actual', 'danger')
            return redirect(url_for('asignacion.index'))

        # Crear nueva asignación
        nueva_asignacion = Asignacion(
            id_docente=id_docente,
            id_asignatura=id_asignatura,
            id_curso=id_curso,
            anio_lectivo=active_config['anio'],
            horas_impartidas=horas_impartidas,
            observaciones=observaciones
        )

        db.session.add(nueva_asignacion)
        db.session.commit()

        # Crear actividad para notificar al docente
        actividad = Actividad(
            tipo='asignacion',
            titulo='Nueva asignación',
            detalle=f'Se te ha asignado la asignatura de {nueva_asignacion.asignatura.nombre} en el curso {nueva_asignacion.curso.nombre}.',
            fecha=datetime.utcnow().date(),
            creado_por=current_user.id,
            id_asignacion=nueva_asignacion.id
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
        
        # Limpiar cache para forzar una actualización en la próxima carga
        clear_asignaciones_cache(active_config['anio'])
        
        flash('Asignación creada exitosamente', 'success')

    except ValueError:
        flash('Datos inválidos en el formulario', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear asignación: {str(e)}', 'danger')

    return redirect(url_for('asignacion.index'))

@asignacion_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar(id):
    asignacion = Asignacion.query.get_or_404(id)
    active_config = get_active_config()

    if not active_config or asignacion.anio_lectivo != active_config['anio']:
        flash('No puedes editar asignaciones de años lectivos no activos', 'danger')
        return redirect(url_for('asignacion.index'))

    try:
        # Obtener datos del formulario
        nuevo_docente = int(request.form['select-docente'])
        nueva_asignatura = int(request.form['select-asignatura'])
        nuevo_curso = int(request.form['select-curso'])
        nuevo_estado = request.form['estado']
        horas_impartidas = request.form.get('horas-impartidas', type=int)
        observaciones = request.form['observaciones']

        # Validar que los nuevos elementos existan
        docente = User.query.filter_by(id=nuevo_docente, rol='docente', estado='activo').first()
        if not docente:
            flash('El docente seleccionado no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        asignatura = Asignatura.query.filter_by(id=nueva_asignatura, estado='activo').first()
        if not asignatura:
            flash('La asignatura seleccionada no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        curso = Curso.query.filter_by(id=nuevo_curso, estado='activo').first()
        if not curso:
            flash('El curso seleccionado no está disponible', 'danger')
            return redirect(url_for('asignacion.index'))

        # Validar duplicados (excluyendo la actual)
        if Asignacion.query.filter(
            Asignacion.id != id,
            Asignacion.id_curso == nuevo_curso,
            Asignacion.id_asignatura == nueva_asignatura,
            Asignacion.anio_lectivo == active_config['anio'],
            Asignacion.estado == 'activo'
        ).first():
            flash('Ya existe una asignación activa para esta combinación', 'danger')
            return redirect(url_for('asignacion.index'))

        # Actualizar asignación
        asignacion.id_docente = nuevo_docente
        asignacion.id_asignatura = nueva_asignatura
        asignacion.id_curso = nuevo_curso
        asignacion.estado = nuevo_estado
        asignacion.horas_impartidas = horas_impartidas
        asignacion.observaciones = observaciones

        db.session.commit()
        
        # Limpiar cache para forzar una actualización en la próxima carga
        clear_asignaciones_cache(active_config['anio'])
        
        flash('Asignación actualizada correctamente', 'success')

    except ValueError:
        flash('Datos inválidos en el formulario', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar asignación: {str(e)}', 'danger')

    return redirect(url_for('asignacion.index'))

@asignacion_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar(id):
    asignacion = Asignacion.query.get_or_404(id)
    active_config = get_active_config()

    if not active_config or asignacion.anio_lectivo != active_config['anio']:
        flash('No puedes eliminar asignaciones de años lectivos no activos', 'danger')
        return redirect(url_for('asignacion.index'))

    if asignacion.estado == 'activo':
        flash('No se puede eliminar una asignación activa. Desactívela primero.', 'danger')
        return redirect(url_for('asignacion.index'))

    try:
        asignacion.eliminado = True
        asignacion.eliminado_por = current_user.id
        asignacion.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Asignación enviada a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar asignación: {str(e)}', 'danger')

    return redirect(url_for('asignacion.index'))


@asignacion_bp.route('/exportar-pdf')
@roles_required('admin', 'docente')
def exportar_pdf():
    try:
        # Lógica de filtrado
        curso_id = request.args.get('curso_id', type=int)
        active_config = get_active_config()

        if not active_config:
            flash('No hay un año lectivo configurado como activo', 'warning')
            return redirect(url_for('asignacion.index'))
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        # Consulta de asignaciones
        query = Asignacion.query.filter_by(anio_lectivo=active_config['anio'])
        if curso_id:
            query = query.filter_by(id_curso=curso_id)
        
        asignaciones = query.order_by(
            Asignacion.id_curso, 
            Asignacion.id_asignatura
        ).all()

        if not asignaciones:
            flash('No hay asignaciones para exportar con los filtros actuales', 'warning')
            return redirect(url_for('asignacion.index'))

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
        
        # Calcular cuántas asignaciones caben por página (20 por página)
        asignaciones_por_pagina = 20
        total_paginas = (len(asignaciones) + asignaciones_por_pagina - 1) // asignaciones_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE ASIGNACIONES")
            
            # Información de año lectivo y filtros aplicados
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, height-58*mm, f"Año lectivo: {active_config['anio']}")
            
            filtros_texto = []
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
            
            # Calcular posiciones centradas para las columnas (7 columnas para asignaciones)
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
            headers = ["N°", "DOCENTE", "CURSO", "ASIGNATURA", "HORAS ASIGNADAS", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener asignaciones para esta página
            inicio = pagina * asignaciones_por_pagina
            fin = inicio + asignaciones_por_pagina
            asignaciones_pagina = asignaciones[inicio:fin]
            
            for i, asignacion in enumerate(asignaciones_pagina, inicio + 1):
                # Preparar datos para cada columna
                datos = [
                    str(i),
                    f"{asignacion.docente.nombre} {asignacion.docente.apellidos}"[:15] + '...' if len(f"{asignacion.docente.nombre} {asignacion.docente.apellidos}") > 18 else f"{asignacion.docente.nombre} {asignacion.docente.apellidos}",
                    asignacion.curso.nombre[:15] + '...' if len(asignacion.curso.nombre) > 18 else asignacion.curso.nombre,
                    asignacion.asignatura.nombre[:15] + '...' if len(asignacion.asignatura.nombre) > 18 else asignacion.asignatura.nombre,
                    str(asignacion.horas_impartidas) if asignacion.horas_impartidas is not None else '-',
                    asignacion.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 6:  # Columna de estado
                        if asignacion.estado.lower() == 'activo':
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(asignaciones)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        filename = f"reporte_asignaciones"
        if curso_id:
            filename += f"_curso{curso_id}"
        filename += ".pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de asignaciones: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('asignacion.index'))