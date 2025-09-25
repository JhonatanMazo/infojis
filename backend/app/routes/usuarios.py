from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import current_user
from io import BytesIO
from datetime import datetime
import sqlalchemy
import bleach 

# --- Base de datos y modelos ---
from app import db
from app.models import User
from app.utils.decorators import admin_required
from app.utils.file_uploads import upload_profile_picture, remove_profile_picture

# --- ReportLab: PDF ---
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os


usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')
    
@usuarios_bp.route('/')
@admin_required
def listar_usuarios():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    estado = request.args.get('estado', None)
    rol = request.args.get('rol', None)
    
    # Validar parámetros de filtro
    estados_permitidos = ['activo', 'inactivo']
    roles_permitidos = ['admin', 'docente']
    
    if estado and estado not in estados_permitidos:
        flash('Estado de usuario no válido', 'warning')
        estado = None
        
    if rol and rol not in roles_permitidos:
        flash('Rol de usuario no válido', 'warning')
        rol = None
    
    query = User.query.filter_by(eliminado=False).order_by(User.creado_en.asc())
    if rol:
        query = query.filter_by(rol=rol)
    
    usuarios = query.paginate(page=page, per_page=per_page, error_out=False)
    
    start_index = (page - 1) * per_page + 1 if usuarios.total > 0 else 0
    end_index = min(page * per_page, usuarios.total) if usuarios.total > 0 else 0
    
    return render_template('views/usuarios.html',
                           usuarios=usuarios,
                           start_index=start_index,
                           end_index=end_index,
                           lista_estados=estados_permitidos,
                           lista_roles=roles_permitidos)

@usuarios_bp.route('/crear', methods=['POST'])
@admin_required
def crear_usuario():
    try:
        # Sanitizar entradas
        nombre = bleach.clean(request.form['nombre'])
        apellidos = bleach.clean(request.form.get('apellidos', ''))
        documento = bleach.clean(request.form['documento'])
        genero = bleach.clean(request.form['genero'])
        email = bleach.clean(request.form['email'])
        password = request.form['contraseña']
        rol = bleach.clean(request.form['rol'])
        estado = bleach.clean(request.form['estado'])
        telefono = bleach.clean(request.form.get('telefono', ''))
        
        # Validar email único
        if User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado', 'danger')
            return redirect(url_for('usuarios.listar_usuarios'))
        
        # Validar documento único
        if User.query.filter_by(documento=documento).first():
            flash('El documento ya está registrado', 'danger')
            return redirect(url_for('usuarios.listar_usuarios'))
        
        nuevo_usuario = User(
            nombre=nombre,
            apellidos=apellidos,
            documento=documento,
            genero=genero,
            email=email,
            rol=rol,
            estado=estado,
            telefono=telefono
        )
        
        nuevo_usuario.set_password(password)
        
        # Subir foto si se proporcionó
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                # Validar tipo
                if not allowed_file(file.filename):
                    flash('Formato de imagen no permitido. Solo se permiten extensiones como JPG, PNG, GIF.', 'warning')
                    return redirect(url_for('usuarios.listar_usuarios'))
                
                # Leer tamaño del archivo
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                max_size = current_app.config.get('MAX_FILE_SIZE', 2 * 1024 * 1024)  # 2MB por defecto
                
                if file_size > max_size:
                    flash(f'La imagen es demasiado grande ({round(file_size / (1024*1024), 2)} MB). El tamaño máximo permitido es {round(max_size / (1024*1024), 2)} MB.', 'warning')
                    return redirect(url_for('usuarios.listar_usuarios'))
                
                filename = upload_profile_picture(file, documento)
                nuevo_usuario.foto = filename
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash('Usuario creado exitosamente', 'success')
        current_app.logger.info(f"Usuario creado: {email}", extra={
            'accion': 'crear_usuario',
            'usuario_id': nuevo_usuario.id,
            'documento': documento
        })
    except sqlalchemy.exc.IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Error de integridad al crear usuario: {str(e)}")
        flash('Error: El documento o email ya existen en el sistema', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al crear usuario: {str(e)}")
        flash('Error al crear usuario', 'danger')
    return redirect(url_for('usuarios.listar_usuarios'))


@usuarios_bp.route('/editar/<int:id>', methods=['POST'])
@admin_required
def editar_usuario(id):
    usuario = User.query.get_or_404(id)
    try:
        # Sanitizar entradas
        usuario.nombre = bleach.clean(request.form['nombre'])
        usuario.apellidos = bleach.clean(request.form.get('apellidos', ''))
        documento_original = usuario.documento
        usuario.documento = bleach.clean(request.form['documento'])
        usuario.genero = bleach.clean(request.form['genero'])
        usuario.email = bleach.clean(request.form['email'])
        usuario.rol = bleach.clean(request.form['rol'])
        # Capture the old state before updating
        old_estado = usuario.estado
        usuario.estado = bleach.clean(request.form['estado'])

        if old_estado == 'activo' and usuario.estado == 'inactivo':
            usuario.regenerate_security_stamp()
            # inactivar de credencial
            if usuario.id == current_user.id:
                logout_user()
                flash('Su credencial ha sido desactivada', 'warning')
                return redirect(url_for('auth.login'))  
            

        # If the user is being reactivated, reset failed attempts
        if old_estado == 'inactivo' and usuario.estado == 'activo':
            usuario.intentos_fallidos = 0 # Reset failed attempts
            usuario.regenerate_security_stamp()  # Regenerate security stamp on reactivation
        usuario.telefono = bleach.clean(request.form.get('telefono', ''))
        
        # Validar email único (excluyendo el propio)
        if User.query.filter(User.id != id, User.email == usuario.email).first():
            flash('El correo electrónico ya está registrado por otro usuario', 'danger')
            return redirect(url_for('usuarios.listar_usuarios'))
        
        # Validar documento único (excluyendo el propio)
        if User.query.filter(User.id != id, User.documento == usuario.documento).first():
            flash('El documento ya está registrado por otro usuario', 'danger')
            return redirect(url_for('usuarios.listar_usuarios'))
        
        # Actualizar contraseña si se proporcionó
        password = request.form.get('contraseña', '')
        if password:
            usuario.set_password(password)
        
        # Actualizar foto si se proporcionó
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '':
                # Validar tipo y tamaño
                if not allowed_file(file.filename):
                    flash('Formato de imagen no permitido', 'danger')
                    return redirect(url_for('usuarios.listar_usuarios'))
                
                # Leer tamaño del archivo
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > current_app.config['MAX_FILE_SIZE']:
                    flash('El archivo excede el tamaño máximo permitido (2MB)', 'danger')
                    return redirect(url_for('usuarios.listar_usuarios'))
                
                # Eliminar la foto anterior si existe
                if usuario.foto:
                    remove_profile_picture(usuario.foto)
                    
                # Subir la nueva
                filename = upload_profile_picture(file, usuario.documento)
                usuario.foto = filename
        
        db.session.commit()
        flash('Usuario actualizado correctamente', 'success')
        current_app.logger.info(f"Usuario actualizado: {usuario.email}", extra={
            'accion': 'editar_usuario',
            'usuario_id': id
        })

        # Si el usuario editado es el usuario actual y fue desactivado, cerrar sesión inmediatamente
        if usuario.id == current_user.id and usuario.estado == 'inactivo':
            from flask_login import logout_user
            logout_user()
            flash('Su credencial ha sido desactivada', 'warning')
            return redirect(url_for('auth.login'))

    except sqlalchemy.exc.IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Error de integridad al editar usuario {id}: {str(e)}")
        flash('Error: El documento o email ya existen en el sistema', 'danger')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al editar usuario {id}: {str(e)}")
        flash('Error al actualizar usuario', 'danger')
    return redirect(url_for('usuarios.listar_usuarios'))

@usuarios_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_usuario(id):
    usuario = User.query.get_or_404(id)

    if usuario.estado == 'activo': 
        flash('No se puede eliminar un usuario activo. Por favor, desactívelo primero desde el formulario de edición.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

    try:
        # No eliminar, solo marcar como eliminado
        usuario.eliminado = True
        usuario.eliminado_por = current_user.id
        usuario.fecha_eliminacion = datetime.utcnow()
        db.session.commit()

        flash('Usuario enviado a la papelera de reciclaje.', 'success')
        current_app.logger.info(f"Usuario enviado a reciclaje: {usuario.email}", extra={
            'accion': 'reciclar_usuario',
            'usuario_id': id
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al eliminar usuario {id}: {str(e)}")
        flash('Error al eliminar usuario', 'danger')
    return redirect(url_for('usuarios.listar_usuarios'))


@usuarios_bp.route('/obtener/<int:id>', methods=['GET'])
@admin_required
def obtener_usuario(id):
    usuario = User.query.get_or_404(id)
    return {
        'id': usuario.id,
        'nombre': usuario.nombre,
        'apellidos': usuario.apellidos,
        'documento': usuario.documento,
        'genero': usuario.genero,
        'email': usuario.email,
        'rol': usuario.rol,
        'estado': usuario.estado,
        'telefono': usuario.telefono,
        'foto': usuario.foto
    }

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
           
           
@usuarios_bp.route('/exportar/pdf')
@admin_required
def exportar_usuarios_pdf():
    try:
        # Lógica de filtrado
        estado = request.args.get('estado')
        rol = request.args.get('rol')
        
        query = User.query
        if estado in ['activo', 'inactivo']:
            query = query.filter_by(estado=estado)
        if rol in ['admin', 'docente']:
            query = query.filter_by(rol=rol)
            
        # Obtener primer nombre y primer apellido del usuario actual
        nombres = current_user.nombre.split()
        apellidos = current_user.apellidos.split() if current_user.apellidos else []
        
        primer_nombre = nombres[0] if nombres else ""
        primer_apellido = apellidos[0] if apellidos else ""
        
        usuario_exportador = f"{primer_nombre} {primer_apellido}".strip()
            
        usuarios = query.order_by(User.creado_en.desc()).all()
        
        if not usuarios:
            flash('No hay usuarios para exportar', 'warning')
            return redirect(url_for('usuarios.listar_usuarios'))

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
        
        # Calcular cuántos usuarios caben por página (20 por página)
        usuarios_por_pagina = 20
        total_paginas = (len(usuarios) + usuarios_por_pagina - 1) // usuarios_por_pagina
        
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
            c.drawCentredString(width/2, height-50*mm, "REPORTE DE USUARIOS")
            
            # Información de filtros aplicados
            filtros_texto = []
            if estado:
                filtros_texto.append(f"Estado: {estado}")
            if rol:
                filtros_texto.append(f"Rol: {rol}")
                
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
            
            # Calcular posiciones centradas para las columnas (7 columnas para usuarios)
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
            headers = ["N°", "NOMBRES", "APELLIDOS", "DOCUMENTO", "CORREO", "ROL", "ESTADO"]
            for i, header in enumerate(headers):
                c.drawCentredString(col_positions[i] + (column_width / 2), current_y - 4*mm, header)
            
            current_y -= 15*mm
            
            # Contenido de la tabla
            c.setFont("Helvetica", 8)
            
            # Obtener usuarios para esta página
            inicio = pagina * usuarios_por_pagina
            fin = inicio + usuarios_por_pagina
            usuarios_pagina = usuarios[inicio:fin]
            
            for i, usuario in enumerate(usuarios_pagina, inicio + 1):
                # Preparar datos para cada columna
                datos = [
                    str(i),
                    usuario.nombre[:15] + '...' if len(usuario.nombre) > 18 else usuario.nombre,
                    usuario.apellidos[:15] + '...' if usuario.apellidos and len(usuario.apellidos) > 18 else (usuario.apellidos or ''),
                    usuario.documento[:12] + '...' if len(usuario.documento) > 15 else usuario.documento,
                    usuario.email[:15] + '...' if len(usuario.email) > 18 else usuario.email,
                    usuario.rol[:10] + '...' if len(usuario.rol) > 13 else usuario.rol,
                    usuario.estado.upper()
                ]
                
                # Dibujar datos centrados en cada columna
                c.setFillColor(black)
                for j, dato in enumerate(datos):
                    if j == 6:  # Columna de estado
                        if usuario.estado.lower() == 'activo':
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
            c.drawCentredString(width/2, 20*mm, f"Total de registros: {len(usuarios)}")
            c.drawCentredString(width/2, 15*mm, f"Página {pagina + 1} de {total_paginas}")
        
        c.save()
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=reporte_usuarios.pdf"
        return response

    except Exception as e:
        current_app.logger.error(f"Error al generar PDF: {e}", exc_info=True)
        flash('Error al generar el reporte PDF: '+str(e),'danger')
        return redirect(url_for('usuarios.listar_usuarios'))
