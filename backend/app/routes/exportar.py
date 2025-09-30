from flask import Blueprint, current_app, make_response, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import current_user
from app.utils.decorators import admin_required
from app.services.configuracion_service import get_active_config
from app import db
from app.models import Matricula, Curso, Calificacion, Asignacion
from io import BytesIO
from datetime import datetime
from sqlalchemy.orm import joinedload
import pandas as pd 
from sqlalchemy import func
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os


exportar_bp = Blueprint('exportar', __name__, url_prefix='/exportar_datos')


@exportar_bp.route('/', methods=['GET'])
@admin_required
def vista_exportar():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    grado = request.args.get('grado', 'todos')
    estado = request.args.get('estado', 'activo')  # Solo activos por defecto


    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None

    # Solo cursos con matrículas activas en el año lectivo actual
    # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
    cursos_ids = db.session.query(Asignacion.id_curso).filter(
        Asignacion.anio_lectivo == anio_lectivo,
        Asignacion.estado == 'activo'
    ).distinct().all()
    cursos_ids = [c[0] for c in cursos_ids]
    cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []

    query = Matricula.query.options(
        joinedload(Matricula.usuario),
        joinedload(Matricula.curso)
    ).order_by(Matricula.apellidos, Matricula.nombres)

    # Excluir siempre a los estudiantes transferidos de la lista principal
    query = query.filter(Matricula.estado != 'transferido')

    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)

    if grado != 'todos':
        query = query.filter(Matricula.id_curso == int(grado))

    if estado and estado != 'todos':
        query = query.filter(Matricula.estado == estado)

    estudiantes = query.paginate(page=page, per_page=per_page, error_out=False)

    start_index = (page - 1) * per_page + 1 if estudiantes.total > 0 else 0
    end_index = min(page * per_page, estudiantes.total) if estudiantes.total > 0 else 0
    
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']

    return render_template('views/estudiantes/exportar-datos.html',
                           cursos=cursos,
                           estudiantes=estudiantes,
                           grado_filtrado=grado,
                           estado_filtrado=estado,
                           start_index=start_index,
                           end_index=end_index)


@exportar_bp.route('/vista_previa', methods=['POST'])
@admin_required
def vista_previa():
    grado = request.form.get('grado')
    estado = request.form.get('estado')
    campos = request.form.getlist('campos[]')

    if not campos:
        campos = ['Nombres', 'Apellidos', 'Documento', 'Grado']

    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None

    query = Matricula.query.options(
        joinedload(Matricula.curso)
    )

    # Excluir siempre a los estudiantes transferidos de la lista principal
    query = query.filter(Matricula.estado != 'transferido')

    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)
    if estado and estado != 'todos':
        query = query.filter(Matricula.estado == estado)
    if grado and grado != 'todos':
        query = query.filter(Matricula.id_curso == int(grado))

    estudiantes = query.limit(20).all()

    promedios_dict = {}
    if 'Promedio General' in campos:
        matricula_ids = [est.id for est in estudiantes]
        promedios_query = db.session.query(
            Calificacion.id_matricula,
            func.avg(Calificacion.nota).label('promedio')
        ).filter(Calificacion.id_matricula.in_(matricula_ids)) \
         .group_by(Calificacion.id_matricula).all()
        promedios_dict = {pm[0]: round(pm[1], 2) for pm in promedios_query}

    data = []
    for est in estudiantes:
        fila = {}
        for campo in campos:
            if campo == 'Nombres':
                fila['Nombres'] = est.nombres
            elif campo == 'Apellidos':
                fila['Apellidos'] = est.apellidos
            elif campo == 'Documento':
                fila['Documento'] = est.documento
            elif campo == 'Fecha Nacimiento':
                fila['Fecha Nacimiento'] = est.fecha_nacimiento.strftime('%Y-%m-%d') if est.fecha_nacimiento else ''
            elif campo == 'Genero':
                fila['Genero'] = est.genero
            elif campo == 'Direccion':
                fila['Direccion'] = est.direccion
            elif campo == 'Telefono':
                fila['Telefono'] = est.telefono
            elif campo == 'Correo':
                fila['Correo'] = est.email
            elif campo == 'Grado':
                fila['Grado'] = est.curso.nombre if est.curso else ''
            elif campo == 'Año Lectivo':
                fila['Año Lectivo'] = est.año_lectivo
            elif campo == 'Estado':
                fila['Estado'] = est.estado
            elif campo == 'Promedio General':
                fila['Promedio General'] = promedios_dict.get(est.id, 0.0)
        data.append(fila)

    return jsonify(data)




@exportar_bp.route('/exportar_estudiantes', methods=['POST'])
@admin_required
def exportar_estudiantes():
    data = request.form
    grado = data.get('grado')
    estado = data.get('estado')
    campos = request.form.getlist('campos[]')
    formato = data.get('formato')

    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    
    # Obtener primer nombre y primer apellido del usuario actual
    nombres = current_user.nombre.split()
    apellidos = current_user.apellidos.split() if current_user.apellidos else []
    
    primer_nombre = nombres[0] if nombres else ""
    primer_apellido = apellidos[0] if apellidos else ""
    
    usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

    query = db.session.query(Matricula).options(
        joinedload(Matricula.usuario),
        joinedload(Matricula.curso),
    )

    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)
    if grado and grado != 'todos':
        query = query.filter(Matricula.id_curso == int(grado))
    if estado and estado != 'todos':
        query = query.filter(Matricula.estado == estado)
        
    # Excluir siempre a los estudiantes transferidos
    query = query.filter(Matricula.estado != 'transferido')

    estudiantes = query.all()

    # Precalcular promedios para todos los estudiantes
    matricula_ids = [est.id for est in estudiantes]
    promedios_query = db.session.query(
        Calificacion.id_matricula,
        func.avg(Calificacion.nota).label('promedio')
    ).filter(Calificacion.id_matricula.in_(matricula_ids)) \
     .group_by(Calificacion.id_matricula).all()
    
    promedios_dict = {pm[0]: round(pm[1], 2) for pm in promedios_query}

    resultados = []
    for est in estudiantes:
        fila = {}
        if 'Nombres' in campos:
            fila['Nombres'] = est.nombres
        if 'Apellidos' in campos:
            fila['Apellidos'] = est.apellidos
        if 'Documento' in campos:
            fila['Documento'] = est.documento
        if 'Fecha Nacimiento' in campos:
            fila['Fecha Nacimiento'] = est.fecha_nacimiento.strftime('%Y-%m-%d') if est.fecha_nacimiento else ''
        if 'Genero' in campos:
            fila['Genero'] = est.genero
        if 'Direccion' in campos:
            fila['Direccion'] = est.direccion
        if 'Telefono' in campos:
            fila['Telefono'] = est.telefono
        if 'Correo' in campos:
            fila['Correo'] = est.email
        if 'Grado' in campos:
            fila['Grado'] = est.curso.nombre if est.curso else ''
        if 'Año Lectivo' in campos:
            fila['Año Lectivo'] = est.año_lectivo
        if 'Estado' in campos:
            fila['Estado'] = est.estado
        if 'Promedio General' in campos:
            fila['Promedio General'] = promedios_dict.get(est.id, 0.0)

        resultados.append(fila)

    if not resultados:
        return jsonify({'error': 'No hay datos para exportar'}), 400

    elif formato == 'excel':
        df = pd.DataFrame(resultados)
        output = BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name='estudiantes.xlsx',
            as_attachment=True
        )

    elif formato == 'csv':
        df = pd.DataFrame(resultados)
        output = BytesIO()
        df.to_csv(output, index=False, sep=';')  # Usa separador punto y coma
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            download_name='estudiantes.csv',
            as_attachment=True
        )

    elif formato == 'pdf':
        try:
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
            color_active = HexColor("#27AE60")
            color_inactive = HexColor("#E74C3C")
            black = HexColor("#000000")
            white = HexColor("#FFFFFF")
            
            # Calcular cuántos estudiantes caben por página
            estudiantes_por_pagina = 20
            total_paginas = (len(resultados) + estudiantes_por_pagina - 1) // estudiantes_por_pagina
            
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
                c.drawCentredString(width/2, height-50*mm, "REPORTE DE ESTUDIANTES")
                
                # Información de filtros aplicados
                info_text = []
                if grado and grado != 'todos':
                    curso_nombre = Curso.query.get(int(grado)).nombre if grado != 'todos' else ''
                    info_text.append(f"Grado: {curso_nombre}")
                if estado and estado != 'todos':
                    info_text.append(f"Estado: {estado}")
                    
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
                
                # Calcular posiciones para las columnas según campos seleccionados
                available_width = width - (2 * margin_left)
                num_columnas = len(campos)
                column_width = available_width / num_columnas if num_columnas > 0 else available_width
                
                # Definir posiciones de las columnas
                col_positions = [
                    margin_left + (i * column_width) for i in range(num_columnas)
                ]
                
                # Encabezados de la tabla en blanco sobre fondo negro
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(white)
                
                # Dibujar encabezados centrados en cada columna
                for i, campo in enumerate(campos):
                    c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, campo[:15])  
                
                current_y -= 15*mm
                
                # Contenido de la tabla
                c.setFont("Helvetica", 8)
                
                # Obtener estudiantes para esta página
                inicio = pagina * estudiantes_por_pagina
                fin = inicio + estudiantes_por_pagina
                estudiantes_pagina = resultados[inicio:fin]
                
                for i, estudiante in enumerate(estudiantes_pagina, inicio + 1):
                    # Dibujar datos centrados en cada columna
                    c.setFillColor(black)
                    for j, campo in enumerate(campos):
                        valor = str(estudiante.get(campo, ''))[:20]  # truncar para no desbordar
                        c.drawCentredString(col_positions[j] + (column_width / 2), current_y, valor)
                    
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
                c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(resultados)}")
                c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
            
            c.save()
            buffer.seek(0)
            
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f"attachment; filename=reporte_estudiantes.pdf"
            return response

        except Exception as e:
            current_app.logger.error(f"Error al generar PDF: {e}", exc_info=True)
            flash('Error al generar el reporte PDF: '+str(e),'danger')
            return redirect(url_for('exportar.vista_exportar'))

    return jsonify({'error': 'Formato no válido'}), 400