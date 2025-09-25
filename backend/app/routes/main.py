from flask import Blueprint, redirect, render_template, url_for

from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('index.html')

@main_bp.route('/politicas')
def politicas_privacidad():
    return render_template('public/politicas-privacidad.html')

@main_bp.route('/terminos')
def terminos_condiciones():
    return render_template('public/terminos-condiciones.html')