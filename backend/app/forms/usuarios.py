from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FileField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, EqualTo
from app.models.user import User

# --- Formulario de Login ---
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="El correo es obligatorio."),
        Email(message="Por favor, introduce una dirección de correo válida.")
    ])
    password = PasswordField('Contraseña', validators=[DataRequired(message="La contraseña es obligatoria.")])
    remember = BooleanField('Recordarme')

# --- Formularios para Restablecer Contraseña ---
class RequestResetForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[DataRequired(message='Este campo es obligatorio.'), Email(message='Por favor ingresa un correo electrónico válido.')])
    submit = SubmitField('Solicitar restablecimiento')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(),
        Length(min=8)
    ])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired(),
        EqualTo('password', message='Las contraseñas deben coincidir.')
    ])
    submit = SubmitField('Restablecer Contraseña')



# --- Formularios para CRUD de Usuarios (Admin) ---
class UsuarioForm(FlaskForm):
    nombre = StringField('Nombres', validators=[DataRequired(), Length(max=100)])
    apellidos = StringField('Apellidos', validators=[Optional(), Length(max=100)])
    documento = StringField('Documento', validators=[DataRequired(), Length(max=30)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    contraseña = PasswordField('Contraseña', validators=[DataRequired(), Length(min=8)])
    genero = SelectField('Género', choices=[
        ('femenino', 'Femenino'),
        ('masculino', 'Masculino'),
        ('otro', 'Otro'),
        ('sin_especificar', 'Prefiero no decir')
    ], validators=[DataRequired()])
    rol = SelectField('Rol', choices=[
        ('admin', 'Administrador'),
        ('docente', 'Docente')
    ], validators=[DataRequired()])
    estado = SelectField('Estado', choices=[
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo')
    ], validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    foto = FileField('Foto de perfil')
    
    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError('Este email ya está registrado')
            
    def validate_documento(self, field):
        if User.query.filter_by(documento=field.data).first():
            raise ValidationError('Documento ya registrado')         

class EditarUsuarioForm(FlaskForm):
    nombre = StringField('Nombres', validators=[DataRequired(), Length(max=100)])
    apellidos = StringField('Apellidos', validators=[Optional(), Length(max=100)])
    documento = StringField('Documento', validators=[DataRequired(), Length(max=30)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    contraseña = PasswordField('Contraseña (dejar en blanco para no cambiar)', 
                             validators=[Optional(), Length(min=8)])
    genero = SelectField('Género', choices=[
        ('femenino', 'Femenino'),
        ('masculino', 'Masculino'),
        ('otro', 'Otro'),
        ('sin_especificar', 'Prefiero no decir')
    ], validators=[DataRequired()])
    rol = SelectField('Rol', choices=[
        ('admin', 'Administrador'),
        ('docente', 'Docente')
    ], validators=[DataRequired()])
    estado = SelectField('Estado', choices=[
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo')
    ], validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    foto = FileField('Foto de perfil')
    
    def __init__(self, original_user, *args, **kwargs):
        super(EditarUsuarioForm, self).__init__(*args, **kwargs)
        self.original_user = original_user
    
    def validate_email(self, field):
        if field.data.lower().strip() != self.original_user.email and \
           User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError('Este email ya está registrado')
            
    def validate_documento(self, field):
        if field.data != self.original_user.documento and \
           User.query.filter_by(documento=field.data).first():
            raise ValidationError('Este documento ya está registrado')  