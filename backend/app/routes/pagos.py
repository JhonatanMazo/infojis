from flask import Blueprint, make_response, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import current_user
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from app import db, mail
from app.models import Curso, Matricula, Pago, Asignacion, Actividad
from app.services.configuracion_service import get_active_config
from app.utils.decorators import admin_required, roles_required
from app.forms.pagos import FiltroPagoForm 
from flask import current_app
import os
from app.utils.pdf_generador import generar_comprobante_pago_pdf
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from flask_mail import Message
pago_bp = Blueprint('pago', __name__, url_prefix='/pagos')

@pago_bp.route('/', methods=['GET'])
@roles_required('admin', 'docente')
def listar_pagos():
    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None

    # Obtener cursos según el rol del usuario
    if current_user.is_admin():
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []
    else:
        # Para docente: solo los cursos asignados en el año lectivo activo
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()

    form = FiltroPagoForm(request.args)
    form.curso.choices = [('', 'Todos')] + [(c.id, c.nombre) for c in cursos]

    curso_id = request.args.get('curso')
    nombre = request.args.get('nombre')
    estado = request.args.get('estado')

    query = Pago.query.join(Matricula).filter(Pago.eliminado == False)
    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)

    # Si es docente, filtrar solo los pagos de sus cursos asignados
    if not current_user.is_admin():
        cursos_asignados_ids = [c.id for c in cursos]
        query = query.filter(Pago.id_curso.in_(cursos_asignados_ids))

    if curso_id:
        query = query.filter(Pago.id_curso == int(curso_id))

    if nombre:
        query = query.filter(
            (Matricula.nombres + ' ' + Matricula.apellidos).ilike(f'%{nombre}%')
        )

    if estado:
        query = query.filter(Pago.estado == estado)

    page = request.args.get('page', 1, type=int)
    pagos = query.order_by(Pago.creado_en.desc()).paginate(page=page, per_page=10)
    
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']

    return render_template('views/pagos.html', pagos=pagos, cursos=cursos, form=form)


@pago_bp.route('/crear', methods=['POST'])
@admin_required
def crear_pago():
    try:
        id_matricula = int(request.form['id_matricula'])
        id_curso = int(request.form['id_curso'])
        concepto = request.form['concepto']
        monto = int(request.form['monto'])
        metodo_pago = request.form['metodo_pago']
        fecha_pago = datetime.strptime(request.form['fecha_pago'], '%Y-%m-%d').date()
        estado = request.form['estado']

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede crear el pago.', 'danger')
            return redirect(url_for('pago.listar_pagos'))
        anio_lectivo = config['anio']

        if fecha_pago.year != anio_lectivo:
            flash(f'La fecha del pago ({fecha_pago.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('pago.listar_pagos'))
        # Validación: verificar si ya existe un pago en esa fecha para el mismo estudiante
        pago_existente = Pago.query.filter_by(
            id_matricula=id_matricula,
            fecha_pago=fecha_pago
        ).first()

        if pago_existente:
            flash('Ya existe un pago registrado para este estudiante en esa misma fecha.', 'danger')
            return redirect(url_for('pago.listar_pagos'))
        nuevo_pago = Pago(
            id_matricula=id_matricula,
            id_curso=id_curso,
            id_usuario=current_user.id,
            concepto=concepto,
            monto=monto,
            metodo_pago=metodo_pago,
            fecha_pago=fecha_pago,
            estado=estado,
        )

        db.session.add(nuevo_pago)
        db.session.commit()

        # Notificar a los docentes del curso
        try:
            config = get_active_config()
            if config and 'anio' in config:
                anio_lectivo = config['anio']
                asignaciones_del_curso = Asignacion.query.filter_by(
                    id_curso=nuevo_pago.id_curso,
                    estado='activo',
                    anio_lectivo=anio_lectivo
                ).all()

                docentes_a_notificar = set()
                for asignacion in asignaciones_del_curso:
                    if asignacion.id_docente != current_user.id:
                        docentes_a_notificar.add(asignacion.id_docente)

                for docente_id in docentes_a_notificar:
                    # Pick one asignacion for this docente
                    asignacion = Asignacion.query.filter_by(
                        id_curso=nuevo_pago.id_curso,
                        id_docente=docente_id,
                        estado='activo',
                        anio_lectivo=anio_lectivo
                    ).first()
                    if asignacion:
                        actividad = Actividad(
                            tipo='pago',
                            titulo='Nuevo pago registrado',
                            detalle=f'Se registró un pago de ${nuevo_pago.monto:,.0f} para el estudiante {nuevo_pago.matricula.nombres} {nuevo_pago.matricula.apellidos} en el curso {nuevo_pago.matricula.curso.nombre}.',
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
            current_app.logger.error(f"Error creando actividad para pago: {str(act_e)}")

        flash('Pago registrado correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear el pago: {str(e)}', 'danger')

    return redirect(url_for('pago.listar_pagos'))




@pago_bp.route('/editar/<int:id>', methods=['POST', 'GET'])
@admin_required
def editar_pago(id):
    pago = Pago.query.get_or_404(id)

    try:
        id_matricula = int(request.form['id_matricula'])
        id_curso = int(request.form['id_curso'])
        concepto = request.form['concepto']
        monto = int(request.form['monto'])
        metodo_pago = request.form['metodo_pago']
        fecha_pago = datetime.strptime(request.form['fecha_pago'], '%Y-%m-%d').date()
        estado = request.form['estado']

        # Obtener el año lectivo activo para validación
        config = get_active_config()
        if not config or 'anio' not in config:
            flash('No hay un año lectivo configurado como activo. No se puede editar el pago.', 'danger')
            return redirect(url_for('pago.listar_pagos'))
        anio_lectivo = config['anio']

        if fecha_pago.year != anio_lectivo:
            flash(f'La fecha del pago ({fecha_pago.year}) no corresponde al año lectivo activo ({anio_lectivo}).', 'danger')
            return redirect(url_for('pago.listar_pagos'))

        # Validación: buscar otro pago con misma matrícula y fecha, excluyendo el actual
        pago_existente = Pago.query.filter(
            Pago.id != pago.id,
            Pago.id_matricula == id_matricula,
            Pago.fecha_pago == fecha_pago
        ).first()

        if pago_existente:
            flash('Ya existe otro pago registrado para este estudiante en esa misma fecha.', 'danger')
            return redirect(url_for('pago.listar_pagos'))

        # Actualizar datos
        pago.id_matricula = id_matricula
        pago.id_curso = id_curso
        pago.concepto = concepto
        pago.monto = monto
        pago.metodo_pago = metodo_pago
        pago.fecha_pago = fecha_pago
        pago.estado = estado

        db.session.commit()
        flash('Pago actualizado correctamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al editar el pago: {str(e)}', 'danger')

    return redirect(url_for('pago.listar_pagos'))



@pago_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_pago(id):
    pago = Pago.query.get_or_404(id)

    if pago.estado.lower() != 'pagado':
        return jsonify({'success': False, 'message': 'Solo se pueden eliminar pagos que ya están pagados'})

    try:
        pago.eliminado = True
        pago.eliminado_por = current_user.id
        pago.fecha_eliminacion = datetime.utcnow()
        db.session.commit()
        flash('Pago enviado a la papelera de reciclaje.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al enviar el pago a la papelera de reciclaje.', 'danger')
    return redirect(url_for('pago.listar_pagos'))

    
@pago_bp.route('/comprobante/<int:id>')
@roles_required('admin', 'docente')
def ver_comprobante(id):
    pago = Pago.query.get_or_404(id)
    matricula = pago.matricula

    if not matricula:
        return 'Matrícula no encontrada', 404

    # Preparar datos para el comprobante
    pago_data = {
        'monto': pago.monto,
        'concepto': pago.concepto,
        'metodo_pago': pago.metodo_pago,
        'estado': pago.estado,
        'fecha_pago': pago.fecha_pago,
        'estudiante_nombre': matricula.nombres,
        'estudiante_apellido': matricula.apellidos,
        'estudiante_documento': getattr(matricula, 'documento', 'N/A'),
        'curso_nombre': pago.curso.nombre if pago.curso else 'N/A'
    }

    # Generar el PDF con el diseño premium
    buffer = generar_comprobante_pago_pdf(id, pago_data)
    
    # Configurar la respuesta
    filename = f"comprobante_pago_{id}.pdf"
    
    return send_file(
        buffer,
        as_attachment=False,
        download_name=filename,
        mimetype='application/pdf'
    )


@pago_bp.route('/enviar_comprobante/<int:id>', methods=['POST'])
@roles_required('admin', 'docente')
def enviar_comprobante(id):
    pago = Pago.query.get_or_404(id)
    matricula = pago.matricula

    if not matricula:
        return jsonify({'success': False, 'message': 'Matrícula no encontrada'})
    
    # Preparar datos para el comprobante (igual que en ver_comprobante)
    pago_data = {
        'monto': pago.monto,
        'concepto': pago.concepto,
        'metodo_pago': pago.metodo_pago,
        'estado': pago.estado,
        'fecha_pago': pago.fecha_pago,
        'estudiante_nombre': matricula.nombres,
        'estudiante_apellido': matricula.apellidos,
        'estudiante_documento': getattr(matricula, 'documento', 'N/A'),
        'curso_nombre': pago.curso.nombre if pago.curso else 'N/A'
    }

    # Generar el PDF premium
    buffer = generar_comprobante_pago_pdf(id, pago_data)
    pdf_data = buffer.getvalue()
    buffer.close()

    # Determinar texto y color según el estado
    if pago.estado.lower() == 'pagado':
        monto_texto = "TOTAL PAGADO"
        monto_color = "#27AE60"  # Verde
    else:
        monto_texto = "TOTAL PENDIENTE"
        monto_color = "#E74C3C"  # Rojo


    # Cuerpo del correo con diseño mejorado
    body = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Comprobante de Pago</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9f9f9;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: #fff;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #2C3E50 0%, #4A6491 100%);
                color: white;
                padding: 25px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 25px;
            }}
            .details {{
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                border-left: 4px solid #E67E22;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                padding-bottom: 10px;
                border-bottom: 1px solid #eee;
            }}
            .detail-row:last-child {{
                border-bottom: none;
                margin-bottom: 0;
                padding-bottom: 0;
            }}
            .detail-label {{
                font-weight: 600;
                color: #2C3E50;
            }}
            .detail-value {{
                text-align: right;
            }}
            .amount {{
                font-size: 20px;
                font-weight: bold;
                text-align: center;
                margin: 25px 0;
                padding: 15px;
                border-radius: 8px;
                border: 1px dashed {monto_color};
                color: {monto_color};
                background-color: {monto_color}15; /* Color con transparencia */
            }}
            .footer {{
                background-color: #2C3E50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 12px;
            }}
            .note {{
                font-style: italic;
                color: #666;
                font-size: 13px;
                text-align: center;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Jardín Infantil Sonrisas</h1>
                <p>Aprendiendo y Sonriendo</p>
            </div>
            
            <div class="content">
                <h2>Comprobante de Pago</h2>
                <p>Estimado/a acudiente de {matricula.nombres} {matricula.apellidos},</p>
                <p>Le informamos sobre el estado de su pago. A continuación encontrará los detalles de su transacción:</p>
                
                <div class="details">
                    <div class="detail-row">
                        <span class="detail-label">Estudiante:</span>
                        <span class="detail-value">{matricula.nombres} {matricula.apellidos}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Curso:</span>
                        <span class="detail-value">{pago.curso.nombre if pago.curso else 'N/A'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Concepto:</span>
                        <span class="detail-value">{pago.concepto}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Método de pago:</span>
                        <span class="detail-value">{pago.metodo_pago}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fecha de pago:</span>
                        <span class="detail-value">{pago.fecha_pago.strftime('%d/%m/%Y')}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Estado:</span>
                        <span class="detail-value" style="color: {'#27AE60' if pago.estado.lower() == 'pagado' else '#E74C3C'}; font-weight: bold;">{pago.estado.upper()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Referencia:</span>
                        <span class="detail-value">PAY-{pago.id:06d}</span>
                    </div>
                </div>
                
                <div class="amount">
                    {monto_texto}: ${pago.monto:,.0f} COP
                </div>
                
                <p style="text-align: center;">
                    <strong>Hemos adjuntado su comprobante de pago en formato PDF</strong> para sus registros.
                </p>
                
                <p class="note">
                    Si tiene alguna pregunta sobre este pago, no dude en contactarnos.<br>
                    Teléfono: 300 149 8933 | Email: jardininfantilsonrisas2023@gmail.com
                </p>
            </div>
            
            <div class="footer">
                <p>© {datetime.now().year} Jardín Infantil Sonrisas. Todos los derechos reservados.</p>
                <p>Este es un mensaje automático, por favor no responda a este correo.</p>
            </div>
        </div>
    </body>
    </html>
    """
    try:
        # Configurar email con Flask-Mail
        msg = Message(
            subject=f'Comprobante de Pago - {pago.concepto} - Jardín Infantil Sonrisas',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[matricula.email],
            html=body
        )

        # Adjuntar PDF
        msg.attach(
            filename=f'comprobante_pago_{id}.pdf',
            content_type='application/pdf',
            data=pdf_data
        )

        mail.send(msg)
        return jsonify({
            'success': True,
            'message': f'Comprobante enviado exitosamente a {matricula.email}'
        })
    except Exception as e:
        current_app.logger.error(f"Error al enviar correo de comprobante: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al enviar correo: {str(e)}'
        })



# Actualizar info_contacto para obtener ID de matrícula
@pago_bp.route('/info_contacto/<int:id>')
@roles_required('admin', 'docente')
def info_contacto(id):
    pago = Pago.query.get_or_404(id)
    m = pago.matricula
    return jsonify({
        'nombre': f"{m.nombres} {m.apellidos}",
        'correo': m.email,
        'whatsapp': m.telefono
    })




# Obtener matrículas por curso (para el select dinámico)
@pago_bp.route('/matriculas_por_curso/<int:id_curso>')
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
            'nombre': f'{m.nombres} {m.apellidos}',
            'foto': url_for('static', filename=f'uploads/profiles/{m.foto}') if m.foto else ''
        })
    return jsonify(data)





# Obtener info de matrícula por ID
@pago_bp.route('/info_matricula/<int:id>')
@roles_required('admin', 'docente')
def info_matricula(id):
    m = Matricula.query.get_or_404(id)
    return jsonify({
        'curso_id': m.id_curso,
        'foto': url_for('static', filename=f'uploads/profiles/{m.foto}') if m.foto else '',
        'id': m.id
    })
    
    
    
@pago_bp.route('/exportar/pdf', methods=['GET'])
@roles_required('admin', 'docente')
def exportar_pagos():
    try:
        data = request.form
        curso_id = request.args.get('curso')
        nombre = request.args.get('nombre')
        estado = request.args.get('estado')
        grado = data.get('grado')
        estado = data.get('estado')
        
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else None

        query = Pago.query

        # Si es docente, filtrar solo los pagos de sus cursos asignados
        if not current_user.is_admin():
            # Obtener cursos asignados al docente
            cursos_asignados = Curso.query.join(Asignacion).filter(
                Asignacion.id_docente == current_user.id,
                Asignacion.estado == 'activo',
                Asignacion.anio_lectivo == anio_lectivo
            ).distinct().all()
            cursos_asignados_ids = [c.id for c in cursos_asignados]
            query = query.filter(Pago.id_curso.in_(cursos_asignados_ids))

        if curso_id:
            query = query.filter_by(id_curso=int(curso_id))

        if estado:
            query = query.filter(Pago.estado.ilike(f"%{estado}%"))

        if nombre:
            query = query.join(Matricula).filter(
                (Matricula.nombres + ' ' + Matricula.apellidos).ilike(f'%{nombre}%')
            )
        if anio_lectivo:
            query = query.filter(Matricula.año_lectivo == anio_lectivo)
        if grado and grado != 'todos':
            query = query.filter(Matricula.id_curso == int(grado))
        if estado and estado != 'todos':
            query = query.filter(Matricula.estado == estado)

        pagos = query.order_by(Pago.creado_en.desc()).all()

        if not pagos:
            flash('No hay pagos para exportar', 'warning')
            return redirect(url_for('pago.listar_pagos'))
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()

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
        color_pagado = HexColor("#27AE60")
        color_pendiente = HexColor("#E74C3C")
        black = HexColor("#000000")
        white = HexColor("#FFFFFF")
        
        # Calcular cuántos pagos caben por página (20 por página)
        pagos_por_pagina = 20
        total_paginas = (len(pagos) + pagos_por_pagina - 1) // pagos_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE PAGOS")
            
            # Información de filtros aplicados
            info_text = []
            if curso_id:
                curso = Curso.query.get(int(curso_id))
                if curso:
                    info_text.append(f"Curso: {curso.nombre}")
            if estado:
                info_text.append(f"Estado: {estado}")
            if nombre:
                info_text.append(f"Nombre: {nombre}")
                
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
            column_width = available_width / 7  # 7 columnas
            
            # Definir posiciones de las columnas centradas
            col_positions = [
                margin_left + (i * column_width) for i in range(7)
            ]
            
            # Encabezados de la tabla en blanco sobre fondo negro
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(white)
            
            # Dibujar encabezados centrados en cada columna
            headers = ["N°", "ESTUDIANTE", "CURSO", "CONCEPTO", "MONTO", "FECHA", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)  
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener pagos para esta página
            inicio = pagina * pagos_por_pagina
            fin = inicio + pagos_por_pagina
            pagos_pagina = pagos[inicio:fin]
            
            for i, pago in enumerate(pagos_pagina, inicio + 1):
                # Preparar datos para cada columna
                estudiante = f"{pago.matricula.nombres} {pago.matricula.apellidos}" if pago.matricula else 'N/A'
                curso = pago.curso.nombre if pago.curso else 'N/A'
                
                datos = [
                    str(i),
                    estudiante[:20] + '...' if len(estudiante) > 23 else estudiante,
                    curso[:15] + '...' if len(curso) > 18 else curso,
                    pago.concepto[:15] + '...' if len(pago.concepto) > 18 else pago.concepto,
                    f"${pago.monto:,.0f}",
                    pago.fecha_pago.strftime('%d/%m/%y'),
                    pago.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 6:  # Columna de estado
                        if pago.estado.lower() == 'pagado':
                            c.setFillColor(color_pagado)
                        else:
                            c.setFillColor(color_pendiente)
                    
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(pagos)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=reporte_pagos.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF de pagos: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('pago.listar_pagos'))