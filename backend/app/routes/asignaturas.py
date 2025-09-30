from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, make_response
from flask_login import current_user
from app import db
from app.models.asignatura import Asignatura
from app.utils.decorators import admin_required
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
import os


asignaturas_bp = Blueprint('asignaturas', __name__, url_prefix='/asignaturas')


@asignaturas_bp.route('/')
@admin_required
def listar_asignaturas():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    estado = request.args.get('estado', None)

    query = Asignatura.query.filter_by(eliminado=False).order_by(Asignatura.nombre.asc())

    if estado:
        query = query.filter_by(estado=estado)

    asignaturas = query.paginate(page=page, per_page=per_page, error_out=False)

    start_index = (page - 1) * per_page + 1 if asignaturas.total > 0 else 0
    end_index = min(page * per_page, asignaturas.total) if asignaturas.total > 0 else 0

    return render_template('views/academico/asignaturas.html',
                           asignaturas=asignaturas,
                           start_index=start_index,
                           end_index=end_index,
                           lista_estados=['activo', 'inactivo'])


@asignaturas_bp.route('/crear', methods=['POST'])
@admin_required
def crear_asignatura():
    try:
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion', None)
        estado = request.form['estado']

        # Validar que el nombre sea único
        asignatura_existente = Asignatura.query.filter_by(nombre=nombre).first()
        if asignatura_existente:
            flash('Ya existe una asignatura con este nombre', 'danger')
            return redirect(url_for('asignaturas.listar_asignaturas'))

        nueva = Asignatura(
            nombre=nombre,
            descripcion=descripcion,
            estado=estado,
            id_usuario=current_user.id
        )
        db.session.add(nueva)
        db.session.commit()
        flash('Asignatura creada exitosamente', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash('Error al crear asignatura', 'danger')
    
    return redirect(url_for('asignaturas.listar_asignaturas'))


@asignaturas_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_asignatura(id):
    asignatura = Asignatura.query.get_or_404(id)
    try:
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion', None)
        estado = request.form['estado']

        # Validar que el nuevo nombre no exista en otra asignatura
        asignatura_existente = Asignatura.query.filter(Asignatura.id != id, Asignatura.nombre == nombre).first()
        if asignatura_existente:
            flash('Ya existe una asignatura con este nombre', 'danger')
            return redirect(url_for('asignaturas.listar_asignaturas'))

        asignatura.nombre = nombre
        asignatura.descripcion = descripcion
        asignatura.estado = estado

        db.session.commit()
        flash('Asignatura actualizada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al editar asignatura', 'danger')
    
    return redirect(url_for('asignaturas.listar_asignaturas'))


@asignaturas_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_asignatura(id):
    asignatura = Asignatura.query.get_or_404(id)
    
    if asignatura.estado == 'activo': 
        flash('No se puede eliminar una asignatura activa. Por favor, desactívela primero desde el formulario de edición.', 'danger')
        return redirect(url_for('asignaturas.listar_asignaturas'))
    
    try:
        asignatura.eliminado = True
        asignatura.eliminado_por = current_user.id
        asignatura.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Asignatura enviada a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar asignatura', 'danger')
    
    return redirect(url_for('asignaturas.listar_asignaturas'))



@asignaturas_bp.route('/exportar/pdf')
@admin_required
def exportar_asignaturas_pdf():
    try:
        estado = request.args.get('estado')

        query = Asignatura.query.order_by(Asignatura.nombre.asc())
        if estado:
            query = query.filter_by(estado=estado)

        asignaturas = query.all()
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        if not asignaturas:
            flash('No hay asignaturas para exportar', 'warning')
            return redirect(url_for('asignaturas.listar_asignaturas', estado=estado))

        # Crear PDF con diseño premium
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar márgenes
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        margin_top = height - (15 * mm)
        
        # Colores premium
        color_primary = HexColor("#2C3E50")
        color_active = HexColor("#27AE60")
        color_inactive = HexColor("#E74C3C")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        # Calcular cuántas asignaturas caben por página (20 por página)
        asignaturas_por_pagina = 20
        total_paginas = (len(asignaturas) + asignaturas_por_pagina - 1) // asignaturas_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE ASIGNATURAS")
            
            # Información de filtros aplicados
            filtros_texto = []
            if estado:
                filtros_texto.append(f"Estado: {estado}")
                
            if filtros_texto:
                c.setFont("Helvetica", 10)
                c.setFillColor(HexColor("#666666"))
                c.drawCentredString(width/2, height-58*mm, f"Filtros aplicados: {', '.join(filtros_texto)}")
            
            # Ajustar posición inicial de la tabla
            current_y = height - 65*mm
            
            # Fondo negro para el encabezado de la tabla
            header_height = 8*mm
            c.setFillColor(black)
            c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
            
            # Calcular posiciones centradas para las columnas (4 columnas para asignaturas)
            available_width = width - (2 * margin_left)
            column_width = available_width / 4  # 4 columnas
            
            # Definir posiciones de las columnas centradas
            col_positions = [
                margin_left + (i * column_width) for i in range(4)
            ]
            
            # Encabezados de la tabla en blanco sobre fondo negro
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "NOMBRE", "DESCRIPCIÓN", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener asignaturas para esta página
            inicio = pagina * asignaturas_por_pagina
            fin = inicio + asignaturas_por_pagina
            asignaturas_pagina = asignaturas[inicio:fin]
            
            for i, asignatura in enumerate(asignaturas_pagina, inicio + 1):
                # Preparar datos para cada columna
                descripcion = asignatura.descripcion[:30] + '...' if asignatura.descripcion and len(asignatura.descripcion) > 33 else (asignatura.descripcion or '')
                
                datos = [
                    str(i),
                    asignatura.nombre[:20] + '...' if len(asignatura.nombre) > 23 else asignatura.nombre,
                    descripcion,
                    asignatura.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 3:  # Columna de estado
                        if asignatura.estado.lower() == 'activo':
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(asignaturas)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        filename = f"reporte_asignaturas.pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de asignaturas: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('asignaturas.listar_asignaturas'))