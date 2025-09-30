from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))

        if current_user.rol != 'admin':
            flash('Acceso denegado: este módulo es solo para administradores.', 'warning')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def docente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))

        if current_user.rol != 'docente':
            flash('Acceso denegado: este módulo es solo para docentes.', 'warning')
            return redirect(url_for('dashboard.index'))  
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.rol not in roles:
                flash('Acceso denegado: no tienes permisos para acceder a este módulo.', 'warning')
                return redirect(url_for('dashboard.index')) 

            return f(*args, **kwargs)
        return decorated_function
    return wrapper
