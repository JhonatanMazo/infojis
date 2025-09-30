from io import BytesIO
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash,  jsonify
from flask_login import current_user
from app.utils.decorators import roles_required
from datetime import datetime
from app import db
from app.models import Curso, Matricula, Periodo, Asignatura, Asignacion, Calificacion
from sqlalchemy import func
from flask import make_response
from app.services.configuracion_service import get_active_config
# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os

posiciones_bp = Blueprint('posiciones', __name__, url_prefix='/posiciones')

@posiciones_bp.route('/')
@roles_required('admin', 'docente')
def index():
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    anio_lectivo = active_config['anio']
    
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

    curso_seleccionado = request.args.get('curso', type=int)

    return render_template('views/informes/posiciones-grados.html', 
                         cursos=cursos,
                         curso_seleccionado=curso_seleccionado)

@posiciones_bp.route('/datos')
@roles_required('admin', 'docente')
def obtener_datos_posiciones():
    config = get_active_config()
    periodo_id = config.get('periodo_id')
    curso_str = request.args.get('curso')

    if not periodo_id:
        return jsonify({'error': 'No hay un período activo configurado.'}), 400

    curso_id = None
    if curso_str and curso_str != 'todos':
        try:
            curso_id = int(curso_str)
        except ValueError:
            return jsonify({'error': 'ID de curso inválido'}), 400

    if current_user.rol != 'admin' and curso_id:
        asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id).first()
        if not asignacion:
            return jsonify({'error': 'No tiene permisos para ver este curso.'}), 403

    periodo = Periodo.query.get_or_404(periodo_id)
    anio_lectivo = config.get('anio')
    if not anio_lectivo:
        return jsonify({'error': 'No hay un año lectivo activo configurado.'}), 400

    try:
        fecha_inicio = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_inicio}", "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_fin}", "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({'error': f"Las fechas del período '{periodo.nombre}' no están configuradas correctamente."}), 400

    # Subquery para promedios
    subquery = db.session.query(
        Calificacion.id_matricula,
        func.avg(Calificacion.nota).label('promedio'),
        func.count(Calificacion.id).label('cantidad_asignaturas')
    ).join(Asignacion, Calificacion.id_asignacion == Asignacion.id).filter(
        Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin)
    ).group_by(Calificacion.id_matricula).subquery()

    # Query principal
    query = db.session.query(
        Matricula,
        subquery.c.promedio,
        subquery.c.cantidad_asignaturas,
        Curso.nombre.label('curso_nombre')
    ).join(
        subquery, Matricula.id == subquery.c.id_matricula
    ).join(
        Curso, Matricula.id_curso == Curso.id
    ).filter(
        Matricula.estado == 'activo',
        subquery.c.cantidad_asignaturas >= 1
    )

    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)
    
    if curso_id:
        query = query.filter(Matricula.id_curso == curso_id)
    elif current_user.rol != 'admin':
        cursos_docente = [asig.id_curso for asig in Asignacion.query.filter_by(id_docente=current_user.id).all()]
        query = query.filter(Matricula.id_curso.in_(cursos_docente))

    query = query.order_by(subquery.c.promedio.desc())

    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    total = query.count()
    resultados = query.offset((page - 1) * per_page).limit(per_page).all()

    datos = []
    for i, (matricula, promedio, cantidad_asignaturas, curso_nombre) in enumerate(resultados):
        datos.append({
            'posicion': (page - 1) * per_page + i + 1,
            'id': matricula.id,
            'nombre': f"{matricula.nombres} {matricula.apellidos}",
            'documento': matricula.documento,
            'curso': curso_nombre,
            'promedio': round(promedio, 2) if promedio else 0.0,
            'foto': matricula.foto,
            'cantidad_asignaturas': cantidad_asignaturas or 0
        })
    
    pages = (total + per_page - 1) // per_page
    return jsonify({
        'data': datos,
        'total_estudiantes': total,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_prev': page > 1,
            'has_next': page < pages,
            'prev_num': page - 1,
            'next_num': page + 1
        }
    })


@posiciones_bp.route('/historial/<int:matricula_id>')
@roles_required('admin', 'docente')
def obtener_historial(matricula_id):
    config = get_active_config()
    periodo_id = config.get('periodo_id')
    if not periodo_id:
        return jsonify({'error': 'No hay un período activo configurado.'}), 400

    anio_lectivo = config.get('anio')
    if not anio_lectivo:
        return jsonify({'error': 'No hay un año lectivo activo configurado.'}), 400

    periodo = Periodo.query.get(periodo_id)
    if not periodo:
        return jsonify({'error': 'Período activo no encontrado'}), 400

    try:
        fecha_inicio = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_inicio}", "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_fin}", "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({'error': f"Las fechas del período '{periodo.nombre}' no están configuradas correctamente."}), 400

    matricula = Matricula.query.get_or_404(matricula_id)
    if anio_lectivo and matricula.año_lectivo != anio_lectivo:
        return jsonify({'error': 'No autorizado para ver este historial'}), 403

    if current_user.rol != 'admin':
        asignacion = Asignacion.query.filter_by(id_curso=matricula.id_curso, id_docente=current_user.id).first()
        if not asignacion:
            return jsonify({'error': 'No tiene permisos para ver este historial.'}), 403

    calificaciones = db.session.query(
        Calificacion,
        Asignatura.nombre
    ).join(
        Asignacion, Calificacion.id_asignacion == Asignacion.id
    ).join(
        Asignatura, Asignacion.id_asignatura == Asignatura.id
    ).filter(
        Calificacion.id_matricula == matricula_id,
        Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin)
    ).all()
    promedio = db.session.query(
        func.avg(Calificacion.nota)
    ).filter(
        Calificacion.id_matricula == matricula_id,
        Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin)
    ).scalar()
    historial = []
    for cal, asignatura_nombre in calificaciones:
        historial.append({
            'asignatura': asignatura_nombre,
            'nota': cal.nota,
            'fecha': cal.fecha_calificacion.strftime('%d/%m/%Y'),
            'observacion': cal.observacion or ''
        })
    return jsonify({
        'historial': historial,
        'promedio': round(promedio, 2) if promedio else 0.0
    })



@posiciones_bp.route('/exportar')
@roles_required('admin', 'docente')
def exportar_posiciones():
    config = get_active_config()
    periodo_id = config.get('periodo_id')
    curso_id = request.args.get('curso', type=int)
    
    if not periodo_id:
        flash('No hay un período activo para exportar', 'error')
        return redirect(url_for('posiciones.index'))

    anio_lectivo = config.get('anio')
    if not anio_lectivo:
        flash('No hay un año lectivo activo configurado.', 'error')
        return redirect(url_for('posiciones.index'))

    if current_user.rol != 'admin' and curso_id:
        asignacion = Asignacion.query.filter_by(id_curso=curso_id, id_docente=current_user.id).first()
        if not asignacion:
            flash('No tiene permisos para exportar este curso.', 'error')
            return redirect(url_for('posiciones.index'))

    try:
        periodo = Periodo.query.get_or_404(periodo_id)
        curso = Curso.query.get(curso_id) if curso_id and curso_id != 'todos' else None
        
        try:
            fecha_inicio = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_inicio}", "%Y-%m-%d").date()
            fecha_fin = datetime.strptime(f"{anio_lectivo}-{periodo.fecha_fin}", "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash(f"Las fechas del período '{periodo.nombre}' no están configuradas correctamente.", 'error')
            return redirect(url_for('posiciones.index'))

        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        subquery = db.session.query(
            Calificacion.id_matricula,
            func.avg(Calificacion.nota).label('promedio'),
            func.count(Calificacion.id).label('cantidad_asignaturas')
        ).join(
            Asignacion, Calificacion.id_asignacion == Asignacion.id
        ).filter(
            Calificacion.fecha_calificacion.between(fecha_inicio, fecha_fin)
        ).group_by(Calificacion.id_matricula).subquery()

        query = db.session.query(
            Matricula,
            subquery.c.promedio,
            subquery.c.cantidad_asignaturas,
            Curso.nombre.label('curso_nombre')
        ).join(
            subquery, Matricula.id == subquery.c.id_matricula
        ).join(
            Curso, Matricula.id_curso == Curso.id
        ).filter(
            Matricula.estado == 'activo',
            subquery.c.cantidad_asignaturas >= 1
        )

        if curso_id and curso_id != 'todos':
            query = query.filter(Matricula.id_curso == curso_id)
        elif current_user.rol != 'admin':
            cursos_docente = [asig.id_curso for asig in Asignacion.query.filter_by(id_docente=current_user.id).all()]
            query = query.filter(Matricula.id_curso.in_(cursos_docente))
            
        if anio_lectivo:
            query = query.filter(Matricula.año_lectivo == anio_lectivo)

        resultados = query.order_by(subquery.c.promedio.desc()).all()

        if not resultados:
            flash('No hay posiciones para exportar', 'warning')
            return redirect(url_for('posiciones.index'))

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        margin_left = 10 * mm
        margin_right = width - (10 * mm)
        margin_top = height - (15 * mm)
        
        color_primary = HexColor("#2C3E50")
        color_gold = HexColor("#FFD700")
        color_silver = HexColor("#C0C0C0")
        color_bronze = HexColor("#CD7F32")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        estudiantes_por_pagina = 20
        total_paginas = (len(resultados) + estudiantes_por_pagina - 1) // estudiantes_por_pagina
        
        for pagina in range(total_paginas):
            if pagina > 0:
                c.showPage()
            
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
                else:
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColor(color_primary)
                    c.drawString(margin_left, height-30*mm, "JARDÍN INFANTIL")
                    c.drawString(margin_left, height-35*mm, "SONRISAS")
            except Exception as e:
                print(f"Error al cargar el logo: {str(e)}")
            
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
            c.drawCentredString(width/2, height-50*mm, "RANKING ACADÉMICO")
            
            info_text = [f"Período: {periodo.nombre}"]
            if curso:
                info_text.append(f"Curso: {curso.nombre}")
            else:
                info_text.append("Todos los cursos")
                
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, height-58*mm, " | ".join(info_text))
            
            current_y = height - 65*mm
            
            header_height = 8*mm 
            c.setFillColor(black)
            c.rect(margin_left, current_y - header_height + 2*mm, width - 2*margin_left, header_height, fill=1, stroke=0)
            
            available_width = width - (2 * margin_left)
            column_width = available_width / 6
            
            col_positions = [ margin_left + (i * column_width) for i in range(6) ]
            
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(white)
            
            headers = ["POSICIÓN", "ESTUDIANTE", "DOCUMENTO", "CURSO", "PROMEDIO", "ASIGNATURAS"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            c.setFont("Helvetica", 8)
            
            inicio = pagina * estudiantes_por_pagina
            fin = inicio + estudiantes_por_pagina
            estudiantes_pagina = resultados[inicio:fin]
            
            for i, (matricula, promedio, cantidad_asignaturas, curso_nombre) in enumerate(estudiantes_pagina, inicio + 1):
                nombre_completo = f"{matricula.nombres} {matricula.apellidos}"
                
                datos = [
                    str(i),
                    nombre_completo[:25] + '...' if len(nombre_completo) > 28 else nombre_completo,
                    matricula.documento or 'N/A',
                    curso_nombre[:15] + '...' if len(curso_nombre) > 18 else curso_nombre,
                    f"{round(promedio, 2) if promedio else 0.0}",
                    str(cantidad_asignaturas or 0)
                ]
                
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 0:
                        if i == 1:
                            c.setFillColor(color_gold)
                        elif i == 2:
                            c.setFillColor(color_silver)
                        elif i == 3:
                            c.setFillColor(color_bronze)
                    
                    c.drawCentredString(col_positions[j] + (column_width / 2), current_y, dato)
                    c.setFillColor(black)
                
                current_y -= 5*mm
                
                c.setStrokeColor(HexColor("#DDDDDD"))
                c.setLineWidth(0.2)
                c.line(margin_left, current_y, margin_right, current_y)
                
                current_y -= 4*mm
            
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(HexColor("#777777"))
            c.drawCentredString(width/2, 25*mm, f"Reporte generado por {usuario_exportador} - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            c.drawCentredString(width/2, 20*mm, f"Total de estudiantes: {len(resultados)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        
        filename = f"ranking_{periodo.nombre.lower().replace(' ', '_')}"
        if curso:
            filename += f"_{curso.nombre.lower().replace(' ', '_')}"
        filename += ".pdf"
        
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de ranking: {e}", exc_info=True)
        flash('Error al generar el ranking en PDF: ' + str(e), 'danger')
        return redirect(url_for('posiciones.index'))
