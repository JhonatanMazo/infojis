from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum, UniqueConstraint
from sqlalchemy.orm import validates
from datetime import datetime
from flask import current_app, url_for
import os
from app.extensions import db
from itsdangerous import URLSafeTimedSerializer as Serializer
from app.utils.file_uploads import get_upload_folder
import uuid


class User(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    __table_args__ = (
        UniqueConstraint('documento', 'email', name='uq_documento_email'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=True)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    genero = db.Column(Enum('femenino', 'masculino', 'otro', 'sin_especificar', name='user_genders'), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(Enum('admin', 'docente', name='user_roles'), nullable=True, default='docente')
    estado = db.Column(Enum('activo', 'inactivo', name='user_status'), default='activo', nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    foto = db.Column(db.String(255), nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acceso = db.Column(db.DateTime, nullable=True)
    intentos_fallidos = db.Column(db.Integer, default=0)
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)
    security_stamp = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), nullable=False)

    # Relaciones
    asignaciones = db.relationship('Asignacion', back_populates='docente', foreign_keys='Asignacion.id_docente', cascade='all, delete-orphan')


    # Validación de email
    @validates('email')
    def validate_email(self, key, email):
        if not email or '@' not in email:
            raise ValueError("Debe proporcionar un email válido")
        return email.lower().strip()

    # Métodos de contraseña
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def regenerate_security_stamp(self):
        self.security_stamp = str(uuid.uuid4())

    # Métodos adicionales
    def __repr__(self):
        return f'<User {self.email}>'

    def is_admin(self):
        return self.rol == 'admin'

    def registrar_acceso(self):
        self.ultimo_acceso = datetime.utcnow()
        self.intentos_fallidos = 0

    def registrar_intento_fallido(self):
        self.intentos_fallidos += 1

    def get_profile_picture_path(self):
        """Devuelve la ruta relativa del archivo en el sistema"""
        if self.foto:
            return os.path.join('uploads', 'profiles', self.foto)
        return None


    def get_profile_picture_url(self):
        """Devuelve la URL para acceder a la imagen verificando su existencia física"""
        if self.foto:
            # Verificar si el archivo existe realmente
            file_path = os.path.join(get_upload_folder('profiles'), self.foto)
            if os.path.exists(file_path):
                return url_for('static', filename=f'uploads/profiles/{self.foto}', _external=False)
                
        # Si no hay foto o el archivo no existe, devolver la imagen por defecto
        return url_for('static', filename='img/default-profile.png', _external=False)

    def delete_profile_picture(self):
        """Elimina la foto de perfil del filesystem"""
        if self.foto:
            try:
                full_path = os.path.join(
                    current_app.root_path, 
                    'static',
                    'uploads',
                    'profiles',
                    self.foto
                )
                if os.path.exists(full_path):
                    os.remove(full_path)
                return True
            except Exception as e:
                current_app.logger.error(f"Error eliminando foto de perfil: {str(e)}")
                return False
        return False

    # Método para generar un token de restablecimiento
    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    # Método estático para verificar el token
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
            user_id = data.get('user_id')
        except Exception:
            return None
        return User.query.get(user_id)
    

    # Método requerido por Flask-Login
    def get_id(self):
        return str(self.id)  # siempre string

    # Flask-Login hereda estos de UserMixin, pero puedes redefinirlos si quieres:
    @property
    def is_active(self):
        # Aquí retornamos True solo si el usuario está activo
        return self.estado == 'activo'

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    # Otros métodos que usas en tu login
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)