from flask import Blueprint, current_app, make_response, redirect, render_template, request, jsonify, send_file, url_for, flash
from flask_login import current_user
from sqlalchemy import func
from app.utils.decorators import roles_required
from datetime import datetime
from app import db
from app.models import Curso, Matricula, Asignatura, Asignacion, Calificacion, ConfiguracionLibro
from app.services.configuracion_service import get_active_config
from io import BytesIO
import pandas as pd
# --- ReportLab: PDF -- - 
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os



libro_final_bp = Blueprint('libro_final', __name__, url_prefix='/libro_final')


def _obtener_datos_libro_final(curso_id, anio_lectivo):
    """
    Función auxiliar para obtener los datos consolidados del libro final, promediando todos los períodos.
    """
    # Subconsulta para calcular el promedio de calificaciones de cada estudiante para el año lectivo.
    subquery = db.session.query(
        Calificacion.id_matricula,
        func.avg(Calificacion.nota).label('promedio_final')
    ).join(Asignacion, Calificacion.id_asignacion == Asignacion.id)\
     .filter(Asignacion.anio_lectivo == anio_lectivo)\
     .group_by(Calificacion.id_matricula).subquery()

    # Consulta principal para obtener los estudiantes del curso con su promedio final.
    estudiantes_con_promedio = db.session.query(
        Matricula,
        subquery.c.promedio_final
    ).outerjoin(subquery, Matricula.id == subquery.c.id_matricula)\
     .filter(
        Matricula.id_curso == curso_id,
        Matricula.estado == 'activo',
        Matricula.año_lectivo == anio_lectivo
    ).order_by(Matricula.apellidos, Matricula.nombres).all()

    config = ConfiguracionLibro.obtener_configuracion_actual()

    datos_estudiantes = []
    for matricula, promedio in estudiantes_con_promedio:
        promedio_final = round(promedio, 1) if promedio is not None else 0.0
        
        if promedio is None:
            estado = "Sin Calificar"
        elif promedio_final >= config.nota_basico:
            estado = "Aprobado"
        else:
            estado = "No Aprobado"

        datos_estudiantes.append({
            'id': matricula.id,
            'nombres': f"{matricula.nombres} {matricula.apellidos}",
            'documento': matricula.documento,
            'foto': matricula.foto or 'default-profile.png',
            'promedio_periodo': promedio_final,
            'estado': estado,
        })
        
    return datos_estudiantes

@libro_final_bp.route('/')
@roles_required('admin', 'docente')
def index():
    """Vista principal del libro final que carga los cursos y datos iniciales."""
    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    
    if current_user.rol == 'admin':
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre.asc()).all() if cursos_ids else []

    else:
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()

    initial_data = {
        'estudiantes': [], 'estadisticas': {'total_estudiantes': 0, 'aprobados': 0, 'no_aprobados': 0, 'sin_calificar': 0},
        'pagination': {'page': 1, 'per_page': 10, 'total': 0, 'pages': 0, 'has_prev': False, 'has_next': False, 'prev_num': 0, 'next_num': 0}
    }
    
    selected_curso_id = None

    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']

    return render_template('views/informes/libro-final.html', 
                           cursos=cursos, 
                           initial_data=initial_data,
                           selected_curso_id=selected_curso_id)

@libro_final_bp.route('/datos')
@roles_required('admin', 'docente')
def obtener_datos_libro():
    """API para obtener datos consolidados para la tabla."""
    curso_id = request.args.get('curso', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    if not curso_id:
        return jsonify({'error': 'Debe seleccionar un grado'}), 400

    if current_user.rol != 'admin':
        asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id).first()
        if not asignacion:
            return jsonify({'error': 'No tiene permisos para ver este curso.'}), 403
    
    try:
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else datetime.now().year
        datos_estudiantes = _obtener_datos_libro_final(curso_id, anio_lectivo)
        
        total_estudiantes = len(datos_estudiantes)
        aprobados = sum(1 for e in datos_estudiantes if e['estado'] == 'Aprobado')
        no_aprobados = sum(1 for e in datos_estudiantes if e['estado'] == 'No Aprobado')
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated_estudiantes = datos_estudiantes[start:end]
        
        return jsonify({
            'estudiantes': paginated_estudiantes,
            'estadisticas': {
                'total_estudiantes': total_estudiantes,
                'aprobados': aprobados,
                'no_aprobados': no_aprobados,
                'sin_calificar': total_estudiantes - aprobados - no_aprobados
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_estudiantes,
                'pages': (total_estudiantes + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': end < total_estudiantes,
                'prev_num': page - 1,
                'next_num': page + 1
            }
        })
    except Exception as e:
        return jsonify({'error': f'Ocurrió un error en el servidor: {str(e)}'}), 500

@libro_final_bp.route('/detalle_estudiante/<int:estudiante_id>')
@roles_required('admin', 'docente')
def detalle_estudiante(estudiante_id):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)

        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else datetime.now().year

        matricula = Matricula.query.get_or_404(estudiante_id)

        estudiante = {
            'id': matricula.id,
            'nombres': f"{matricula.nombres} {matricula.apellidos}",
            'documento': matricula.documento,
            'foto': matricula.foto or 'default-profile.png'
        }

        config_libro = ConfiguracionLibro.obtener_configuracion_actual()
        nota_basico = config_libro.nota_basico if config_libro else 3.0

        calificaciones_query = db.session.query(
            Asignatura.nombre.label('asignatura'),
            func.avg(Calificacion.nota).label('promedio_asignatura'),
            func.count(Calificacion.id).label('cantidad_notas')
        ).join(Asignacion, Asignacion.id_asignatura == Asignatura.id).join(Calificacion, Calificacion.id_asignacion == Asignacion.id).filter(
             Calificacion.id_matricula == estudiante_id,
             Asignacion.anio_lectivo == anio_lectivo
         ).group_by(Asignatura.nombre).all()
        if current_user.rol != 'admin':
            calificaciones_query = [cal for cal in calificaciones_query if Asignacion.query.filter_by(id_asignatura=Asignatura.query.filter_by(nombre=cal.asignatura).first().id, id_docente=current_user.id, estado='activo', anio_lectivo=anio_lectivo).first()]

        calificaciones = []
        promedio_general = 0
        total_asignaturas = len(calificaciones_query)

        for cal in calificaciones_query:
            promedio_asig = round(float(cal.promedio_asignatura), 1) if cal.promedio_asignatura is not None else 0.0
            estado_asig = 'Aprobado' if promedio_asig >= nota_basico else 'No Aprobado'

            calificaciones.append({
                'asignatura': cal.asignatura,
                'promedio': promedio_asig,
                'cantidad_notas': cal.cantidad_notas,
                'estado': estado_asig
            })
            promedio_general += promedio_asig

        promedio_general = round(promedio_general / total_asignaturas, 1) if total_asignaturas > 0 else 0.0
        estado_general = 'Aprobado' if promedio_general >= nota_basico else 'No Aprobado'

        # Paginación para calificaciones
        total_calificaciones = len(calificaciones)
        start = (page - 1) * per_page
        end = start + per_page
        calificaciones_paginadas = calificaciones[start:end]

        total_pages = (total_calificaciones + per_page - 1) // per_page

        return jsonify({
            **estudiante,
            'calificaciones': calificaciones_paginadas,
            'promedio_general': promedio_general,
            'estado_general': estado_general,
            'nota_basico': nota_basico,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_calificaciones,
                'pages': total_pages,
                'has_prev': page > 1,
                'has_next': end < total_calificaciones,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if end < total_calificaciones else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@libro_final_bp.route('/configuracion', methods=['GET', 'POST'])
@roles_required('admin')
def configuracion():
    if request.method == 'POST':
        try:
            nota_superior = request.form.get('nota_superior', type=float)
            nota_alto = request.form.get('nota_alto', type=float)
            nota_basico = request.form.get('nota_basico', type=float)

            if not (0 <= nota_basico < nota_alto < nota_superior <= 5.0):
                return jsonify({'success': False, 'error': 'Las notas de desempeño no son válidas. Deben estar entre 0 y 5, y seguir el orden Básico < Alto < Superior.'}), 400

            config = ConfiguracionLibro.obtener_configuracion_actual()
            config.nota_superior = nota_superior
            config.nota_alto = nota_alto
            config.nota_basico = nota_basico
            config.id_usuario = current_user.id
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Configuración guardada correctamente'})
        except ValueError:
            return jsonify({'success': False, 'error': 'El nivel de aprobación debe ser un número válido'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # GET
    try:
        config = ConfiguracionLibro.obtener_configuracion_actual()
        return jsonify(config.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@libro_final_bp.route('/exportar_excel')
@roles_required('admin', 'docente')
def exportar_excel():
    """Exportar libro final a Excel."""
    curso_id = request.args.get('curso', type=int)
    
    if not curso_id:
        return "Parámetros incompletos", 400

    if current_user.rol != 'admin':
        asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id).first()
        if not asignacion:
            return "No tiene permisos para exportar este curso.", 403
    
    try:
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else datetime.now().year
        datos_estudiantes = _obtener_datos_libro_final(curso_id, anio_lectivo)
        curso = Curso.query.get(curso_id)

        df_data = []
        for i, estudiante in enumerate(datos_estudiantes, 1):
            df_data.append({
                'N°': i,
                'Estudiante': estudiante['nombres'],
                'Documento': estudiante['documento'],
                'Promedio': estudiante['promedio_periodo'],
                'Estado': estudiante['estado']
            })

        df = pd.DataFrame(df_data)
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Libro Final')
        output.seek(0)
        
        filename = f"Libro_Final_{curso.nombre}_{anio_lectivo}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return str(e), 500


@libro_final_bp.route('/exportar_pdf')
@roles_required('admin', 'docente')
def exportar_pdf():
    """Exportar libro final a PDF con diseño premium similar al de cursos."""
    curso_id = request.args.get('curso', type=int)

    if not curso_id:
        flash('Debe seleccionar un curso para exportar.', 'warning')
        return redirect(url_for('libro_final.index'))

    if current_user.rol != 'admin':
        asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id).first()
        if not asignacion:
            flash('No tiene permisos para exportar este curso.', 'error')
            return redirect(url_for('libro_final.index'))

    try:
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else datetime.now().year
        datos_estudiantes = _obtener_datos_libro_final(curso_id, anio_lectivo)
        if not datos_estudiantes:
            flash('No hay estudiantes matriculados en este curso para generar el informe.', 'warning')
            return redirect(url_for('libro_final.index'))
        
        curso = Curso.query.get(curso_id)
        config_libro = ConfiguracionLibro.obtener_configuracion_actual()
        
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Configurar márgenes
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        margin_top = height - (15 * mm)
        
        # Colores premium (mismo diseño que cursos)
        color_primary = HexColor("#2C3E50")
        color_active = HexColor("#27AE60")
        color_inactive = HexColor("#E74C3C")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        # Calcular cuántos estudiantes caben por página (20 por página)
        estudiantes_por_pagina = 20
        total_paginas = (len(datos_estudiantes) + estudiantes_por_pagina - 1) // estudiantes_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE LIBRO FINAL")
            
            # Información del curso y año lectivo
            info_text = [
                f"Curso: {curso.nombre}",
                f"Año Lectivo: {anio_lectivo}",
                f"Nivel de Aprobación: {config_libro.nota_basico}"
            ]
                
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
            headers = ["N°", "ESTUDIANTE", "DOCUMENTO", "PROMEDIO", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)  
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener estudiantes para esta página
            inicio = pagina * estudiantes_por_pagina
            fin = inicio + estudiantes_por_pagina
            estudiantes_pagina = datos_estudiantes[inicio:fin]
            
            for i, estudiante in enumerate(estudiantes_pagina, inicio + 1):
                # Preparar datos para cada columna
                nombres = estudiante['nombres'][:25] + '...' if len(estudiante['nombres']) > 28 else estudiante['nombres']
                documento = estudiante['documento'] or 'N/A'
                promedio = f"{estudiante['promedio_periodo']:.1f}"
                estado = estudiante['estado'].upper()
                
                datos = [str(i), nombres, documento, promedio, estado]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 4:  # Columna de estado
                        if estudiante['estado'].lower() == 'aprobado':
                            c.setFillColor(color_active)
                        elif estudiante['estado'].lower() == 'no aprobado':
                            c.setFillColor(color_inactive)
                        else:
                            c.setFillColor(HexColor("#F39C12"))  # Amarillo/naranja para "Sin Calificar"
                    
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
            c.drawCentredString(width/2, 20*mm, f"Total de estudiantes: {len(datos_estudiantes)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=libro_final_{curso.nombre.replace(' ', '_')}_{anio_lectivo}.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF del libro final: {e}", exc_info=True)
        flash('Error al generar el libro final en PDF: ' + str(e), 'danger')
        return redirect(url_for('libro_final.index'))


@libro_final_bp.route('/exportar_individual_pdf/<int:estudiante_id>')
@roles_required('admin', 'docente')
def exportar_individual_pdf(estudiante_id):
    """Exportar detalle individual de calificaciones a PDF con diseño premium similar al de exportar datos."""
    try:
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else datetime.now().year

        matricula = Matricula.query.get_or_404(estudiante_id)
        if current_user.rol != 'admin':
            asignacion = Asignacion.query.filter_by(id_curso=matricula.id_curso, id_docente=current_user.id).first()
            if not asignacion:
                flash('No tiene permisos para exportar los detalles de este estudiante.', 'error')
                return redirect(url_for('libro_final.index'))

        curso = Curso.query.get(matricula.id_curso)
        config_libro = ConfiguracionLibro.obtener_configuracion_actual()

        calificaciones_query = db.session.query(
            Asignatura.nombre.label('asignatura'),
            func.avg(Calificacion.nota).label('promedio_asignatura'),
            func.count(Calificacion.id).label('cantidad_notas')
        ).join(Asignacion, Asignacion.id_asignatura == Asignatura.id).join(Calificacion, Calificacion.id_asignacion == Asignacion.id).filter(
             Calificacion.id_matricula == estudiante_id,
             Asignacion.anio_lectivo == anio_lectivo
         ).group_by(Asignatura.nombre).order_by(Asignatura.nombre).all()

        calificaciones = []
        promedio_general = 0
        asignaturas_calificadas = [cal for cal in calificaciones_query if cal.promedio_asignatura is not None]
        total_asignaturas_calificadas = len(asignaturas_calificadas)

        for cal in calificaciones_query:
            promedio_asig = round(cal.promedio_asignatura, 1) if cal.promedio_asignatura is not None else 0.0
            estado_asig = 'Aprobado' if promedio_asig >= config_libro.nota_basico else 'No Aprobado'
            calificaciones.append({
                'asignatura': cal.asignatura,
                'promedio': promedio_asig,
                'cantidad_notas': cal.cantidad_notas,
                'estado': estado_asig
            })
            if cal.promedio_asignatura is not None:
                promedio_general += promedio_asig

        promedio_general = round(promedio_general / total_asignaturas_calificadas, 1) if total_asignaturas_calificadas > 0 else 0.0
        estado_general = 'Aprobado' if promedio_general >= config_libro.nota_basico else 'No Aprobado'

        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Configurar márgenes
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        margin_top = height - (15 * mm)

        # Colores premium (mismo diseño que exportar datos)
        color_primary = HexColor("#2C3E50")
        color_active = HexColor("#27AE60")
        color_inactive = HexColor("#E74C3C")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")

        # Página única para estudiante individual
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
        c.drawCentredString(width/2, height-50*mm, "CALIFICACIONES INDIVIDUAL")

        # Información del estudiante y curso (dos líneas)
        info_line1 = [
            f"Estudiante: {matricula.nombres} {matricula.apellidos}",
            f"Documento: {matricula.documento}",
            f"Curso: {curso.nombre}"
        ]

        info_line2 = [
            f"Año Lectivo: {anio_lectivo}",
            f"Nivel de Aprobación: {config_libro.nota_basico}"
        ]

        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(width/2, height-58*mm, " | ".join(info_line1))
        c.drawCentredString(width/2, height-63*mm, " | ".join(info_line2))

        # Resumen general
        current_y = height - 70*mm
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(color_primary)
        c.drawString(margin_left, current_y, "Resumen General")
        c.setStrokeColor(color_primary)
        c.setLineWidth(0.5)
        c.line(margin_left, current_y - 2*mm, margin_right, current_y - 2*mm)

        current_y -= 10*mm
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(black)
        c.drawString(margin_left, current_y, f"Promedio General: {promedio_general:.1f}")
        c.drawString(margin_left + 80*mm, current_y, f"Estado: {estado_general}")

        # Ajustar posición inicial de la tabla
        current_y -= 15*mm

        # Fondo negro para el encabezado de la tabla
        header_height = 8*mm
        c.setFillColor(black)
        c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)

        # Calcular posiciones centradas para las columnas (4 columnas)
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
        headers = ["ASIGNATURA", "N° NOTAS", "PROMEDIO", "ESTADO"]
        for i, header in enumerate(headers):
            c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)

        current_y -= 15*mm

        # Contenido de la tabla
        c.setFont("Helvetica", 8)

        for i, calificacion in enumerate(calificaciones):
            # Preparar datos para cada columna
            asignatura = calificacion['asignatura'][:20] + '...' if len(calificacion['asignatura']) > 23 else calificacion['asignatura']
            cantidad_notas = str(calificacion['cantidad_notas'])
            promedio = f"{calificacion['promedio']:.1f}"
            estado = calificacion['estado'].upper()

            datos = [asignatura, cantidad_notas, promedio, estado]

            # Dibujar datos centrados en cada columna
            c.setFillColor(black)
            for j, dato in enumerate(datos):
                if j == 3:  # Columna de estado
                    if calificacion['estado'].lower() == 'aprobado':
                        c.setFillColor(color_active)
                    elif calificacion['estado'].lower() == 'no aprobado':
                        c.setFillColor(color_inactive)
                    else:
                        c.setFillColor(HexColor("#F39C12"))  # Amarillo/naranja para otros estados

                c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                c.setFillColor(black)  # Restablecer color para las siguientes columnas

            current_y -= 5*mm

            # Línea separadora tenue
            c.setStrokeColor(HexColor("#DDDDDD"))
            c.setLineWidth(0.2)
            c.line(margin_left, current_y, margin_right, current_y)

            current_y -= 4*mm

        # Pie de página
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(HexColor("#777777"))
        c.drawCentredString(width/2, 25*mm, f"Reporte generado por {usuario_exportador} - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        c.drawCentredString(width/2, 20*mm, f"Estudiante: {matricula.nombres} {matricula.apellidos}")
        c.drawCentredString(width/2, 15*mm, "Página 1 de 1")

        c.save()
        buffer.seek(0)

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=detalle_individual_{matricula.nombres.replace(' ', '_')}_{matricula.apellidos.replace(' ', '_')}_{anio_lectivo}.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF individual del estudiante: {e}", exc_info=True)
        flash('Error al generar el detalle individual en PDF: ' + str(e), 'danger')
        return redirect(url_for('libro_final.index'))
