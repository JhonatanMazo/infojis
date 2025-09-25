from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app.utils.decorators import roles_required
from app import db
from app.utils.file_uploads import upload_profile_picture, remove_profile_picture
from flask import current_app
import os
from app.services.configuracion_service import get_active_config

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


perfil_bp = Blueprint('perfil', __name__, url_prefix='/perfil')

@perfil_bp.route('/')
@roles_required('admin', 'docente')
def ver_perfil():
    return render_template('views/perfil.html')

@perfil_bp.route('/actualizar', methods=['POST'])
@roles_required('admin', 'docente')
def actualizar_perfil():
    try:
        # Actualizar datos básicos
        current_user.nombre = request.form['nombre']
        current_user.apellidos = request.form.get('apellidos', '')
        current_user.email = request.form['email']
        current_user.telefono = request.form.get('telefono', '')
        current_user.genero = request.form['genero']
        
        db.session.commit()
        flash('Perfil actualizado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar el perfil', 'danger')
    
    return redirect(url_for('perfil.ver_perfil'))

@perfil_bp.route('/cambiar-contrasena', methods=['POST'])
@roles_required('admin', 'docente')
def cambiar_contrasena():
    try:
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Verificar contraseña actual
        if not current_user.check_password(current_password):
            flash('La contraseña actual es incorrecta', 'danger')
            return redirect(url_for('perfil.ver_perfil'))
        
        # Verificar que las nuevas contraseñas coincidan
        if new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden', 'danger')
            return redirect(url_for('perfil.ver_perfil'))
        
        # Cambiar contraseña
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Contraseña actualizada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al cambiar la contraseña', 'danger')
    
    return redirect(url_for('perfil.ver_perfil'))


@perfil_bp.route('/cambiar-foto', methods=['POST'])
@roles_required('admin', 'docente')
def cambiar_foto():
    try:
        if 'foto' not in request.files:
            flash('No se seleccionó ninguna imagen', 'warning')
            return redirect(url_for('perfil.ver_perfil'))

        file = request.files['foto']

        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'warning')
            return redirect(url_for('perfil.ver_perfil'))

        if not allowed_file(file.filename):
            flash('Formato de imagen no permitido. Solo se permiten archivos JPG, JPEG, PNG y GIF.', 'danger')
            return redirect(url_for('perfil.ver_perfil'))

        # Validar tamaño del archivo
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        max_size = current_app.config.get('MAX_FILE_SIZE', 2 * 1024 * 1024)  # 2MB por defecto
        if file_size > max_size:
            flash('La imagen excede el tamaño máximo permitido (2MB).', 'danger')
            return redirect(url_for('perfil.ver_perfil'))

        #  Eliminar la foto anterior si existe
        if current_user.foto:
            remove_profile_picture(current_user.foto)

        # Subir nueva foto
        filename = upload_profile_picture(file, current_user.documento)
        current_user.foto = filename
        db.session.commit()

        flash('Foto de perfil actualizada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al cambiar la foto de perfil: {str(e)}")
        flash('Error al cambiar la foto de perfil', 'danger')

    return redirect(url_for('perfil.ver_perfil'))



@perfil_bp.route('/eliminar-foto', methods=['POST'])
@roles_required('admin', 'docente')
def eliminar_foto():
    if current_user.foto:
        if remove_profile_picture(current_user.foto):
            current_user.foto = None
            db.session.commit()
            flash('Foto de perfil eliminada correctamente', 'success')
        else:
            flash('No se pudo eliminar la foto de perfil del servidor.', 'danger')
    else:
        flash('No hay foto que eliminar.', 'warning')
    
    return redirect(url_for('perfil.ver_perfil'))
