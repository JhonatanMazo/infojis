from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app, jsonify
from flask_login import current_user
from app import db
from app.models import Periodo, AnioPeriodo
from app.models.configuracion import SystemConfig
from app.utils.decorators import admin_required
from datetime import datetime
from io import BytesIO

# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os


periodos_bp = Blueprint('periodos', __name__, url_prefix='/periodos')


@periodos_bp.route('/')
@admin_required
def listar_periodos():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    nombre_periodo = request.args.get('nombre', None)

    query = Periodo.query.filter_by(eliminado=False).order_by(Periodo.nombre.asc())

    if nombre_periodo:
        query = query.filter_by(nombre=nombre_periodo)

    periodos = query.paginate(page=page, per_page=per_page, error_out=False)

    start_index = (page - 1) * per_page + 1 if periodos.total > 0 else 0
    end_index = min(page * per_page, periodos.total) if periodos.total > 0 else 0

    # Obtener todos los nombres de los períodos para el filtro
    todos_los_periodos = Periodo.query.filter_by(eliminado=False).order_by(Periodo.nombre.asc()).all()

    return render_template('views/academico/periodos.html',
                           periodos=periodos,
                           start_index=start_index,
                           end_index=end_index,
                           todos_los_periodos=todos_los_periodos,
                           nombre_seleccionado=nombre_periodo)
    
    
def verificar_cruce_fechas(fecha_inicio_str, fecha_fin_str, periodo_id=None):
    """
    Verifica si las fechas proporcionadas se cruzan con algún período existente.
    """
    # Convertir las fechas MM-DD a objetos date con año dummy
    fecha_inicio = datetime.strptime(f"2000-{fecha_inicio_str}", "%Y-%m-%d").date()
    fecha_fin = datetime.strptime(f"2000-{fecha_fin_str}", "%Y-%m-%d").date()
    
    # Obtener todos los períodos existentes (excepto el que se está editando, si aplica)
    query = Periodo.query.filter_by(eliminado=False)
    if periodo_id:
        query = query.filter(Periodo.id != periodo_id)
    
    periodos_existentes = query.all()
    
    for periodo in periodos_existentes:
        # Convertir fechas del período existente
        existente_inicio = datetime.strptime(f"2000-{periodo.fecha_inicio}", "%Y-%m-%d").date()
        existente_fin = datetime.strptime(f"2000-{periodo.fecha_fin}", "%Y-%m-%d").date()
        
        # Verificar si hay cruce de fechas
        if (fecha_inicio <= existente_fin and fecha_fin >= existente_inicio):
            return True, periodo.nombre
    
    return False, None


@periodos_bp.route('/crear', methods=['POST'])
@admin_required
def crear_periodo():
    try:
        nombre = request.form['nombre']
        fecha_inicio_str = request.form['fecha_inicio']
        fecha_fin_str = request.form['fecha_fin']

        # Validate date format and real dates
        try:
            # Use a dummy year (e.g., 2000) for date parsing and comparison
            fecha_inicio = datetime.strptime(f"2000-{fecha_inicio_str}", "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(f"2000-{fecha_fin_str}", "%Y-%m-%d").date()
        except ValueError:
            flash('Formato de fecha inválido o fecha no real (ej. 02-30). Use MM-DD.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))

        # Validate end date is after start date
        if fecha_fin <= fecha_inicio:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))

        # Check if a period with the same name already exists
        if Periodo.query.filter_by(nombre=nombre, eliminado=False).first():
            flash('Ya existe un período con este nombre.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))
            
        # Verificar cruce de fechas con períodos existentes
        hay_cruce, periodo_cruce = verificar_cruce_fechas(fecha_inicio_str, fecha_fin_str)
        if hay_cruce:
            flash(f'Las fechas se cruzan con el período "{periodo_cruce}". Por favor, elija otras fechas.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))

        nuevo = Periodo(
            nombre=nombre,
            fecha_inicio=fecha_inicio_str, # Store as MM-DD string
            fecha_fin=fecha_fin_str,       # Store as MM-DD string
            id_usuario=current_user.id
        )
        db.session.add(nuevo)
        db.session.commit()

        # Create AnioPeriodo entries for all existing academic years
        anios_existentes = SystemConfig.query.all()
        for anio_config in anios_existentes:
            nuevo_anio_periodo = AnioPeriodo(
                anio_lectivo=anio_config.anio,
                periodo_id=nuevo.id,
                fecha_inicio=fecha_inicio_str,
                fecha_fin=fecha_fin_str,
                estado="inactivo"  # Initially inactive
            )
            db.session.add(nuevo_anio_periodo)
        db.session.commit()

        flash('Período creado exitosamente', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al crear período: {str(e)}")
        flash('Error al crear período', 'danger')

    return redirect(url_for('periodos.listar_periodos'))


@periodos_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_periodo(id):
    periodo = Periodo.query.get_or_404(id)
    try:
        nombre = request.form['nombre']
        fecha_inicio_str = request.form['fecha_inicio']
        fecha_fin_str = request.form['fecha_fin']

        # Validate date format and real dates
        try:
            # Use a dummy year (e.g., 2000) for date parsing and comparison
            fecha_inicio = datetime.strptime(f"2000-{fecha_inicio_str}", "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(f"2000-{fecha_fin_str}", "%Y-%m-%d").date()
        except ValueError:
            flash('Formato de fecha inválido o fecha no real (ej. 02-30). Use MM-DD.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))

        # Validate end date is after start date
        if fecha_fin <= fecha_inicio:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))
        
        # Check if a period with the same name already exists (excluding the current one)
        if Periodo.query.filter(Periodo.nombre == nombre, Periodo.id != id, Periodo.eliminado == False).first():
            flash('Ya existe un período con este nombre.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))
            
        # Verificar cruce de fechas con períodos existentes (excluyendo el actual)
        hay_cruce, periodo_cruce = verificar_cruce_fechas(fecha_inicio_str, fecha_fin_str, id)
        if hay_cruce:
            flash(f'Las fechas se cruzan con el período "{periodo_cruce}". Por favor, elija otras fechas.', 'danger')
            return redirect(url_for('periodos.listar_periodos'))

        periodo.nombre = nombre
        periodo.fecha_inicio = fecha_inicio_str
        periodo.fecha_fin = fecha_fin_str

        # Update AnioPeriodo entries for all years with the new dates
        AnioPeriodo.query.filter_by(periodo_id=id).update({
            'fecha_inicio': fecha_inicio_str,
            'fecha_fin': fecha_fin_str
        })

        db.session.commit()
        flash('Período actualizado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al editar período {id}: {str(e)}")
        flash('Error al editar período', 'danger')

    return redirect(url_for('periodos.listar_periodos'))



@periodos_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_periodo(id):
    periodo = Periodo.query.get_or_404(id)
    
    if AnioPeriodo.query.filter_by(periodo_id=id, estado='activo').first():
        flash('No se puede eliminar un período que está activo en algún año lectivo. Desactívelo primero.', 'danger')
        return redirect(url_for('periodos.listar_periodos'))
    
    try:
        periodo.eliminado = True
        periodo.eliminado_por = current_user.id
        periodo.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Período enviado a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al eliminar período {id}: {str(e)}")
        flash('Error al eliminar período', 'danger')

    return redirect(url_for('periodos.listar_periodos'))


@periodos_bp.route('/json/all')
@admin_required
def get_all_periodos_json():
    periodos = Periodo.query.filter_by(eliminado=False).all()
    periodos_data = [{
        'id': p.id, 
        'nombre': p.nombre,
        'fecha_inicio': p.fecha_inicio,
        'fecha_fin': p.fecha_fin
    } for p in periodos]
    return jsonify(periodos_data)


@periodos_bp.route('/exportar/pdf')
@admin_required
def exportar_periodos_pdf():
    try:
        estado = request.args.get('estado')
        # Query AnioPeriodo to get periods with their associated years and dates
        query = AnioPeriodo.query.join(Periodo).order_by(AnioPeriodo.anio_lectivo.desc(), Periodo.nombre.asc())
        if estado:
            query = query.filter(AnioPeriodo.estado == estado)

        anio_periodos = query.all()
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        if not anio_periodos:
            flash('No hay períodos para exportar', 'warning')
            return redirect(url_for('periodos.listar_periodos', estado=estado))

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
        
        # Calcular cuántos períodos caben por página (20 por página)
        periodos_por_pagina = 20
        total_paginas = (len(anio_periodos) + periodos_por_pagina - 1) // periodos_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE PERÍODOS")
            
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
            
            # Calcular posiciones centradas para las columnas (5 columnas para períodos)
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
            headers = ["N°", "NOMBRE", "FECHA INICIO", "FECHA FIN", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener períodos para esta página
            inicio = pagina * periodos_por_pagina
            fin = inicio + periodos_por_pagina
            anio_periodos_pagina = anio_periodos[inicio:fin]
            
            for i, anio_periodo in enumerate(anio_periodos_pagina, inicio + 1):
                # Reconstruct full dates using Periodo's month/day and AnioPeriodo's year
                try:
                    start_month, start_day = map(int, anio_periodo.periodo.fecha_inicio.split('-'))
                    end_month, end_day = map(int, anio_periodo.periodo.fecha_fin.split('-'))
                    
                    full_start_date = datetime(anio_periodo.anio_lectivo, start_month, start_day)
                    full_end_date = datetime(anio_periodo.anio_lectivo, end_month, end_day)
                    
                    fecha_inicio_str = full_start_date.strftime('%d/%m/%Y')
                    fecha_fin_str = full_end_date.strftime('%d/%m/%Y')
                except ValueError:
                    fecha_inicio_str = "Fecha Inválida"
                    fecha_fin_str = "Fecha Inválida"

                # Preparar datos para cada columna
                datos = [
                    str(i),
                    anio_periodo.periodo.nombre[:20] + '...' if len(anio_periodo.periodo.nombre) > 23 else anio_periodo.periodo.nombre,
                    fecha_inicio_str,
                    fecha_fin_str,
                    anio_periodo.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 4:  # Columna de estado
                        if anio_periodo.estado.lower() == 'activo':
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(anio_periodos)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        filename = f"reporte_periodos.pdf"

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename={filename}"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de períodos: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('periodos.listar_periodos'))

@periodos_bp.route('/json/<int:anio>')
@admin_required
def get_periodos_json(anio):
    # Get all AnioPeriodo entries for the given anio_lectivo, joining with Periodo to filter non-deleted
    anio_periodos = AnioPeriodo.query.filter_by(anio_lectivo=anio).join(Periodo).filter(Periodo.eliminado == False).all()

    # Extract the Periodo objects from these AnioPeriodo entries
    periodos_data = []
    for ap in anio_periodos:
        if ap.periodo: # Ensure the periodo relationship is loaded
            periodos_data.append({'id': ap.periodo.id, 'nombre': ap.periodo.nombre})

    return jsonify(periodos_data)  