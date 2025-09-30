from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from app.models import User
from werkzeug.routing import BuildError
from app import db
from app.extensions import LoginManager, mail
from flask_mail import Message
import logging
from app.services.configuracion_service import get_active_config
from app.models import AnioPeriodo
from app.forms.usuarios import LoginForm, RequestResetForm, ResetPasswordForm



# Definición única del Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
auth_logger = logging.getLogger('auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        remember = form.remember.data

        user = User.query.filter_by(email=email).first()
        auth_logger.info(f"Usuario encontrado: {user.email if user else 'No encontrado'}")

        if user:
            auth_logger.info(f"Estado del usuario ANTES de refrescar: {user.estado}")
            db.session.refresh(user)
            auth_logger.info(f"Estado del usuario DESPUÉS de refrescar: {user.estado}")

        if not user:
            flash('Credenciales incorrectas.', 'danger')
            return render_template('auth/login.html', form=form)

        if user.estado == 'inactivo':
            auth_logger.warning(f"Intento de login de usuario inactivo: {user.email}")
            flash('Su cuenta en estos momentos está inactiva.', 'warning')
            return render_template('auth/login.html', form=form)

        password_check_result = user.check_password(password)
        auth_logger.info(f"Resultado de la verificación de contraseña para {user.email}: {'Éxito' if password_check_result else 'Fallo'}")

        if not password_check_result:
            user.registrar_intento_fallido()
            if user.intentos_fallidos >= current_app.config['MAX_FAILED_ATTEMPTS'] and user.rol != 'admin':
                user.estado = 'inactivo'
                db.session.commit()
                auth_logger.warning(f"Cuenta bloqueada por intentos fallidos: {user.email}")
                flash('Su cuenta ha sido bloqueada por demasiados intentos fallidos. Contacte al administrador.', 'danger')
            else:
                db.session.commit()
                flash('Credenciales incorrectas.', 'danger')
            return render_template('auth/login.html', form=form)
        
        if user.rol == 'docente':
            active_config = get_active_config()
            anio_lectivo = active_config.get('anio') if active_config else None

            if not anio_lectivo:
                flash('No puede iniciar sesión porque no hay un año lectivo configurado como activo.', 'warning')
                return render_template('auth/login.html', form=form)

            anio_periodo_activo = AnioPeriodo.query.filter_by(estado='activo', anio_lectivo=anio_lectivo).first()
            if not anio_periodo_activo:
                flash('No puede iniciar sesión porque no hay un período activo para el año lectivo actual.', 'warning')
                return render_template('auth/login.html', form=form)

        login_user(user, remember=remember)
        session['security_stamp'] = user.security_stamp
        current_app.logger.debug(f"DEBUG: User {user.id} logged in. Session security stamp: {session['security_stamp']}")
        user.registrar_acceso()
        db.session.commit()
        flash(f'Bienvenido/a {user.nombre}', 'success')

        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html', form=form)



# --- Funciones y rutas para restablecer contraseña ---

@auth_bp.route('/request-reset', methods=['GET', 'POST'])
def request_reset():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RequestResetForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        if user:
            if send_reset_email(user):
                flash('Se ha enviado un correo con las instrucciones para restablecer tu contraseña.', 'info')
            else:
                flash('Hubo un error al enviar el correo. Por favor intenta nuevamente.', 'danger')
        else:
            flash('No se encontró una cuenta con ese correo electrónico.', 'danger')

        return redirect(url_for('auth.login'))

    return render_template('auth/contraseña.html', title='Restablecer Contraseña', form=form)
    
    
def send_reset_email(user):
    token = user.get_reset_token()
    try:
        # Asegurar contexto de aplicación
        with current_app.app_context():
            reset_url = url_for('auth.reset_token', token=token, _external=True)
        
        msg = Message('Restablecimiento de Contraseña - Infojis',
                     sender=current_app.config['MAIL_DEFAULT_SENDER'],
                     recipients=[user.email])
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Restablecer Contraseña</h2>
            <p>Hemos recibido una solicitud para restablecer tu contraseña.</p>
            <a href="{reset_url}" 
               style="display: inline-block; background-color: #3498db; color: white; 
                      padding: 10px 20px; text-decoration: none; border-radius: 5px; 
                      margin: 20px 0;">
               Restablecer Contraseña
            </a>
            <p>Si no solicitaste este cambio, ignora este mensaje.</p>
            <p style="color: #7f8c8d; font-size: 0.9em;">
               El enlace expirará en 30 minutos.
            </p>
        </div>
        """
        
        mail.send(msg)
        current_app.logger.info(f"Email de restablecimiento enviado a {user.email} | URL: {reset_url}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email: {str(e)}")
        return False           
    


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        # Redirigir al índice si ya está logueado
        return redirect(url_for('main.index'))

    user = User.verify_reset_token(token)
    if user is None:
        flash('El token es inválido o ha expirado.', 'warning')
        # Intentamos url_for, si falla usamos ruta literal
        try:
            return redirect(url_for('auth.request_reset'))
        except BuildError:
            return redirect('/auth/request-reset')

    form = ResetPasswordForm()

    if form.validate_on_submit():
        # La validación (contraseñas coinciden, longitud mínima) ya la hace el formulario.
        nueva_contra = form.password.data
        user.set_password(nueva_contra)
        db.session.commit()
        flash('Tu contraseña ha sido actualizada. Ya puedes iniciar sesión.', 'success')
        
        # Redirigir al login, con fallback si falla url_for
        try:
            return redirect(url_for('auth.login'))
        except BuildError:
            return redirect('/auth/login')

    return render_template('auth/reset_token.html',
                           title='Restablecer Contraseña',
                           form=form,
                           token=token)




# --- Endpoints de API para AJAX ---

@auth_bp.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Endpoint para obtener token CSRF (para APIs)."""
    return jsonify({'csrf_token': generate_csrf()})



@auth_bp.route('/api/contact-request', methods=['POST'])
def contact_request():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email') or not data.get('message'):
        return jsonify({'success': False, 'error': 'Faltan datos.'}), 400

    name = data.get('name')
    email = data.get('email')
    message_body = data.get('message')

    try:
        admin_email = current_app.config.get('MAIL_USERNAME')
        if not admin_email:
             auth_logger.error("No se ha configurado un email de administrador para recibir solicitudes.")
             return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500
        msg = Message(f'Nueva solicitud de acceso de: {name}',
                      recipients=[admin_email])
        msg.body = f"""
        Ha recibido una nueva solicitud de acceso desde el formulario de login.

        Nombre: {name}
        Email: {email}
        Mensaje:
        {message_body}
        """
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Solicitud enviada.'})

    except Exception as e:
        auth_logger.error(f"Error procesando solicitud de contacto: {str(e)}")
        return jsonify({'success': False, 'error': 'No se pudo enviar la solicitud.'}), 500
    


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/check_active', methods=['GET'])
@login_required
def check_active():
    """Endpoint para verificar si el usuario actual está activo."""
    return jsonify({'active': current_user.is_active})

@auth_bp.route('/force_logout')
@login_required
def force_logout():
    logout_user()
    flash('Su credencial ha sido desactivada', 'warning')
    return redirect(url_for('auth.login'))



login_manager = LoginManager()
@login_manager.user_loader
def load_user(user_id):
    print(f"[DEBUG] Flask-Login intenta cargar user_id={user_id}")
    user = User.query.get(int(user_id))
    if user:
        print(f"[DEBUG] Usuario encontrado: {user.email} (estado={user.estado})")
    else:
        print("[DEBUG] Usuario NO encontrado")

    if user and user.is_active:
        return user
    return None