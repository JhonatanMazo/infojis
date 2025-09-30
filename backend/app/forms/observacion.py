from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, DateField, FileField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf.file import FileAllowed

class ObservacionForm(FlaskForm):
    curso = SelectField('Grado', coerce=int, validators=[DataRequired()])
    estudiante = SelectField('Estudiante', coerce=int, validators=[DataRequired()])
    tipo = SelectField('Tipo de Observación', choices=[
        ('académica', 'Académica'),
        ('asistencia', 'Asistencia'),
        ('disciplinaria', 'Disciplinaria')
    ], validators=[DataRequired()])
    fecha = DateField('Fecha', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[DataRequired()])
    detalles = FileField('Adjuntar Archivos', validators=[
        FileAllowed(['pdf', 'jpg', 'png', 'jpeg', 'docx'])
    ])
    submit = SubmitField('Guardar')


class DummyDeleteForm(FlaskForm):
    """Formulario vacío solo para incluir token CSRF en formularios de eliminación."""
    pass
