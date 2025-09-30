from logging import config
from flask import Blueprint, current_app, make_response, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.utils.decorators import admin_required
from app import db
from app.models import Curso, Matricula, SystemConfig
from sqlalchemy import false
from app.services.configuracion_service import get_active_config
from io import BytesIO
from datetime import datetime
import json
import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.asignacion import Asignacion

transferencia_bp = Blueprint('transferir', __name__, url_prefix='/transferir')

@transferencia_bp.route('/', methods=['GET'])
@admin_required
def index():
    curso_filtrado = request.args.get('curso', type=int)
    estado_filtrado = request.args.get('estado')
    page = request.args.get('page', 1, type=int)
    page_historial = request.args.get('page_historial', 1, type=int)

    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    
    # Obtener todos los años configurados para el selector de destino
    anio_lectivo_actual = active_config.get('anio')
    todos_los_anios = SystemConfig.query.filter(
        SystemConfig.anio != anio_lectivo_actual
    ).order_by(SystemConfig.anio.desc()).all()

    
    # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
    cursos_ids = db.session.query(Asignacion.id_curso).filter(
        Asignacion.anio_lectivo == anio_lectivo_actual,
        Asignacion.estado == 'activo'
    ).distinct().all()
    cursos_ids = [c[0] for c in cursos_ids]
    cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []

    
    matriculas_query = Matricula.query.filter(false())
    filtros_aplicados = False

    if curso_filtrado or estado_filtrado:
        filtros_aplicados = True
        matriculas_query = Matricula.query.join(Curso).filter(Curso.estado == 'activo')
        
        if curso_filtrado:
            matriculas_query = matriculas_query.filter(Matricula.id_curso == curso_filtrado)
        
        if estado_filtrado and estado_filtrado != 'todos':
            matriculas_query = matriculas_query.filter(Matricula.estado == estado_filtrado)

    # Filtrar por año lectivo actual
    matriculas_query = matriculas_query.filter(Matricula.año_lectivo == anio_lectivo_actual)
    
    # Excluir estudiantes ya transferidos de la lista de candidatos
    matriculas_query = matriculas_query.filter(Matricula.estado != 'transferido')

    matriculas = matriculas_query.order_by(
        Matricula.apellidos, 
        Matricula.nombres
    ).paginate(
        page=page, 
        per_page=10,
        error_out=False
    )

    historial_query = Matricula.query.filter(
        Matricula.fecha_transferencia.isnot(None)
    )

    historial_transferencias = historial_query.order_by(
        Matricula.fecha_transferencia.desc()
    ).paginate(
        page=page_historial, 
        per_page=10,
        error_out=False
    )

    return render_template(
        'views/estudiantes/transferir.html',
        cursos=cursos,
        matriculas=matriculas,
        historial_transferencias=historial_transferencias,
        curso_filtrado=curso_filtrado,
        estado_filtrado=estado_filtrado,
        todos_los_anios=todos_los_anios,
        anio_lectivo_actual=anio_lectivo_actual,
        filtros_aplicados=filtros_aplicados,
        datetime=datetime
    )
    

@transferencia_bp.route('/transferir-multiples', methods=['POST'])
@admin_required
def transferir_multiples():
    if current_user.rol not in ['admin', 'coordinador']:
        flash('No tienes permisos para realizar esta acción', 'danger')
        return redirect(url_for('transferir.index'))

    matriculas_ids_json = request.form.get('estudiantes_ids_json')
    curso_destino_id = request.form.get('curso_destino')
    anio_destino = request.form.get('anio_destino', type=int)
    observaciones = request.form.get('observaciones', '')
    fecha_transferencia = request.form.get('fecha_transferencia', datetime.now().date())

    if not matriculas_ids_json or not curso_destino_id:
        flash('Debes seleccionar estudiantes y un curso de destino', 'warning')
        return redirect(url_for('transferir.index'))

    if not anio_destino:
        flash('Debes seleccionar un año lectivo de destino.', 'warning')
        return redirect(url_for('transferir.index'))

    curso_destino = Curso.query.filter_by(id=curso_destino_id, estado='activo').first()
    if not curso_destino:
        flash('El curso de destino no existe o no está activo', 'danger')
        return redirect(url_for('transferir.index'))

    try:
        matriculas_ids = json.loads(matriculas_ids_json)
        
        if not matriculas_ids:
            flash('No se seleccionaron estudiantes', 'warning')
            return redirect(url_for('transferir.index'))
            
        transferidos = 0
        for matricula_id in matriculas_ids:
            matricula = Matricula.query.get(matricula_id)

            # --- INICIO DE LA CORRECCIÓN ---
            # Verificar si ya existe una matrícula para ese estudiante en el año de destino
            matricula_existente_destino = Matricula.query.filter_by(
                documento=matricula.documento,
                año_lectivo=anio_destino
            ).first()

            if matricula_existente_destino:
                flash(f'El estudiante {matricula.nombres} {matricula.apellidos} ya tiene una matrícula en el año {anio_destino}. No se puede transferir.', 'warning')
                continue # Saltar a la siguiente iteración
            # --- FIN DE LA CORRECCIÓN ---

            if matricula and matricula.id_curso != curso_destino_id:

                # Marcar la matrícula original como transferida
                matricula.estado = 'transferido'
                matricula.observaciones_transferencia = f"Transferido a {curso_destino.nombre} ({anio_destino}). {observaciones}"
                
                # Crear una nueva matrícula en el año y curso de destino
                nueva_matricula = Matricula(
                    nombres=matricula.nombres,
                    apellidos=matricula.apellidos,
                    genero=matricula.genero,
                    documento=matricula.documento,
                    email=matricula.email,
                    telefono=matricula.telefono,
                    direccion=matricula.direccion,
                    fecha_nacimiento=matricula.fecha_nacimiento,
                    foto=matricula.foto,
                    id_curso=curso_destino_id,
                    año_lectivo=anio_destino,
                    estado='activo', # La nueva matrícula estará activa
                    fecha_matricula=datetime.now().date(),
                    # Campos de transferencia en la nueva matrícula
                    fecha_transferencia=datetime.now(),
                    transferido_por=' '.join([
                        current_user.nombre.split()[0] if current_user.nombre else "",
                        current_user.apellidos.split()[0] if current_user.apellidos else ""
                    ]).strip(),
                    observaciones_transferencia=observaciones,
                    curso_origen=f"{matricula.curso.nombre if matricula.curso else 'N/A'} ({matricula.año_lectivo})"
                )
                db.session.add(nueva_matricula)
                transferidos += 1

        db.session.commit()
        flash(f'{transferidos} estudiantes transferidos exitosamente al curso {curso_destino.nombre} del año {anio_destino}', 'success')
    
    except json.JSONDecodeError:
        flash('Error en el formato de los datos de estudiantes.', 'danger')
    except KeyError:
        flash('Faltan datos en el formulario para la transferencia.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al transferir estudiantes: {str(e)}', 'danger')
    
    return redirect(url_for('transferir.index'))

@transferencia_bp.route('/eliminar_historial/<int:id>', methods=['POST'])
@admin_required
def eliminar_historial(id):
    try:
        matricula = Matricula.query.get_or_404(id)
        
        # Limpiar los campos de transferencia
        matricula.fecha_transferencia = None
        matricula.transferido_por = None
        matricula.observaciones_transferencia = None
        matricula.curso_origen = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Registro de transferencia eliminado correctamente'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al eliminar registro: {str(e)}'
        }), 500

@transferencia_bp.route('/exportar-historico-pdf')
@admin_required
def exportar_historial_pdf():
    try:
        # Aceptar un año desde la URL, si no, usar el activo
        anio_a_exportar = request.args.get('anio', type=int)
        if not anio_a_exportar:
            config = get_active_config()
            anio_a_exportar = config['anio'] if config and 'anio' in config else None
        
        if not anio_a_exportar:
            flash('No se pudo determinar un año lectivo para exportar.', 'danger')
            return redirect(url_for('transferir.index'))

        transferencias = Matricula.query.filter(
            Matricula.fecha_transferencia.isnot(None)
        ).order_by(Matricula.fecha_transferencia.desc()).all()
        
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

        if not transferencias:
            flash('No hay historial de transferencias para exportar', 'warning')
            return redirect(url_for('transferir.index'))

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
        
        # Calcular cuántos registros caben por página
        registros_por_pagina = 20
        total_paginas = (len(transferencias) + registros_por_pagina - 1) // registros_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "HISTORIAL DE TRANSFERENCIAS")

            # Información del año lectivo del reporte
            c.setFont("Helvetica", 10)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, height-58*mm, f"Año Lectivo del Reporte: {anio_a_exportar}")
            
            # Ajustar posición inicial de la tabla
            current_y = height - 65*mm  
            
            # Fondo negro para el encabezado de la tabla
            header_height = 8*mm 
            c.setFillColor(black)
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
            c.setFillColor(white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "ESTUDIANTE", "DOCUMENTO", "C. ORIGEN", "C. DESTINO", "TRANSFERIDO POR", "FECHA"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)  
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener registros para esta página
            inicio = pagina * registros_por_pagina
            fin = inicio + registros_por_pagina
            registros_pagina = transferencias[inicio:fin]
            
            for i, transferencia in enumerate(registros_pagina, inicio + 1):
                # Preparar datos para cada columna (asegurando que no sean None)
                nombre_completo = f"{transferencia.apellidos or ''} {transferencia.nombres or ''}".strip()
                documento = transferencia.documento or ''
                curso_origen = transferencia.curso_origen or 'N/A'
                curso_destino = transferencia.curso.nombre if transferencia.curso else 'N/A'
                transferido_por = transferencia.transferido_por or 'N/A'
                fecha = transferencia.fecha_transferencia.strftime('%d/%m/%Y') if transferencia.fecha_transferencia else 'N/A'
                
                # Acortar textos si son muy largos
                if len(nombre_completo) > 23:
                    nombre_completo = nombre_completo[:20] + '...'
                
                if len(curso_origen) > 18:
                    curso_origen = curso_origen[:15] + '...'
                
                if len(curso_destino) > 18:
                    curso_destino = curso_destino[:15] + '...'
                
                datos = [
                    str(i),
                    nombre_completo,
                    documento,
                    curso_origen,
                    curso_destino,
                    transferido_por,
                    fecha
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    c.drawCentredString(col_positions[j] + (column_width / 2), current_y, str(dato))
                
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(transferencias)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=historial_transferencias.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('transferir.index'))