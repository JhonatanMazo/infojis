from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import current_user
from app import db
from app.models import Curso, Matricula
from app.services.configuracion_service import get_active_config
from app.utils.decorators import admin_required
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
import os



cursos_bp = Blueprint('cursos', __name__, url_prefix='/cursos')

@cursos_bp.route('/datos')
def obtener_cursos():
    """Obtener todos los cursos activos para el libro final"""
    try:
        cursos = Curso.query.filter_by(estado='activo').order_by(Curso.nombre.asc()).all()
        datos_cursos = [{
            'id': curso.id,
            'nombre': curso.nombre,
            'descripcion': curso.descripcion
        } for curso in cursos]
        
        return {'success': True, 'cursos': datos_cursos}
    except Exception as e:
        current_app.logger.error(f"Error al obtener cursos: {e}")
        return {'success': False, 'error': str(e)}




@cursos_bp.route('/')
@admin_required
def listar_cursos():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    estado = request.args.get('estado', None)

    

    query = Curso.query.filter_by(eliminado=False).order_by(Curso.nombre.asc())

    if estado:
        query = query.filter_by(estado=estado)

    cursos = query.paginate(page=page, per_page=per_page, error_out=False)

    for curso in cursos.items:
        # Contar estudiantes activos solo del año lectivo actual
        count = Matricula.query.filter_by(id_curso=curso.id, estado='activo').count()
        curso.num_estudiantes = count
        
    start_index = (page - 1) * per_page + 1 if cursos.total > 0 else 0
    end_index = min(page * per_page, cursos.total) if cursos.total > 0 else 0

    return render_template('views/academico/cursos.html',
                         cursos=cursos,
                         start_index=start_index,
                         end_index=end_index,
                         lista_estados=['activo', 'inactivo'])

@cursos_bp.route('/crear', methods=['POST'])
@admin_required
def crear_curso():
    try:
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion', None)
        estado = request.form['estado']

        # Validar que el nombre sea único
        if Curso.query.filter_by(nombre=nombre).first():
            flash('Ya existe un curso con este nombre', 'danger')
            return redirect(url_for('cursos.listar_cursos'))

        nuevo = Curso(
            nombre=nombre,
            descripcion=descripcion,
            estado=estado,
            id_usuario=current_user.id
        )

        db.session.add(nuevo)
        db.session.commit()
        flash('Curso creado exitosamente', 'success')
    
    except ValueError:
        flash('Datos numéricos inválidos', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al crear curso: {e}")
        flash(f'Error al crear curso: {str(e)}', 'danger')
    
    return redirect(url_for('cursos.listar_cursos'))

@cursos_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_curso(id):
    curso = Curso.query.get_or_404(id)
    try:
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion', None)
        estado = request.form['estado']

        # Validar que el nuevo nombre no exista en otro curso
        if Curso.query.filter(Curso.id != id, Curso.nombre == nombre).first():
            flash('Ya existe un curso con este nombre', 'danger')
            return redirect(url_for('cursos.listar_cursos'))

        curso.nombre = nombre
        curso.descripcion = descripcion
        curso.estado = estado

        db.session.commit()
        flash('Curso actualizado correctamente', 'success')
    except ValueError:
        flash('Datos numéricos inválidos', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al editar curso {id}: {e}")
        flash(f'Error al editar curso: {str(e)}', 'danger')
    
    return redirect(url_for('cursos.listar_cursos'))


@cursos_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_curso(id):
    curso = Curso.query.get_or_404(id)
    
    if curso.estado == 'activo': 
        flash('No se puede eliminar un curso activo. Por favor, desactívelo primero desde el formulario de edición.', 'danger')
        return redirect(url_for('cursos.listar_cursos'))
    
    try:
        curso.eliminado = True
        curso.eliminado_por = current_user.id
        curso.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Curso enviado a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al eliminar curso {id}: {e}")
        flash('Error al eliminar curso', 'danger')
    
    return redirect(url_for('cursos.listar_cursos'))


@cursos_bp.route('/exportar/pdf')
@admin_required
def exportar_cursos_pdf():
    try:
        estado = request.args.get('estado')

        query = Curso.query.order_by(Curso.nombre.asc())
        if estado:
            query = query.filter_by(estado=estado)

        cursos = query.all()

        if not cursos:
            flash('No hay cursos para exportar', 'warning')
            return redirect(url_for('cursos.listar_cursos', estado=estado))
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        # Obtener el número de estudiantes registrados por curso
        for curso in cursos:
            count = Matricula.query.filter_by(id_curso=curso.id, estado='activo').count()
            curso.num_estudiantes = count

        # Crear PDF con diseño premium similar al de pagos
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
        
        # Calcular cuántos cursos caben por página (20 por página)
        cursos_por_pagina = 20
        total_paginas = (len(cursos) + cursos_por_pagina - 1) // cursos_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE CURSOS")
            
            # Información de filtros aplicados y configuración
            info_text = []
            if estado:
                info_text.append(f"Filtro: Estado = {estado}")
                
            if info_text:
                c.setFont("Helvetica", 10)
                c.setFillColor(HexColor("#666666"))
                c.drawCentredString(width/2, height-58*mm, " | ".join(info_text))
            
            # Ajustar posición inicial de la tabla para ganar espacio
            current_y = height - 65*mm  
            
            # Fondo negro para el encabezado de la tabla
            header_height = 8*mm 
            c.setFillColor(black)
            c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
            
            # Calcular posiciones centradas para las columnas
            available_width = width - (2 * margin_left)
            column_width = available_width / 5  # 5 columnas
            
            # Definir posiciones de las columnas centradas
            col_positions = [
                margin_left + (i * column_width) for i in range(5)
            ]
            
            # Encabezados de la tabla en blanco sobre fondo negro
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "NOMBRE", "EST. REGISTRADOS", "DESCRIPCIÓN", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)  
            
            current_y -= 15*mm  # Reducido de 12mm a 10mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener cursos para esta página
            inicio = pagina * cursos_por_pagina
            fin = inicio + cursos_por_pagina
            cursos_pagina = cursos[inicio:fin]
            
            for i, curso in enumerate(cursos_pagina, inicio + 1):
                # Preparar datos para cada columna
                descripcion = curso.descripcion[:30] + '...' if curso.descripcion and len(curso.descripcion) > 35 else (curso.descripcion or '')
                
                datos = [
                    str(i),
                    curso.nombre[:20] + '...' if len(curso.nombre) > 23 else curso.nombre,
                    str(curso.num_estudiantes),
                    descripcion,
                    curso.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 4:  # Columna de estado
                        if curso.estado.lower() == 'activo':
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(cursos)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=reporte_cursos.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('cursos.listar_cursos'))