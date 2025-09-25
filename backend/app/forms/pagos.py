from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import Optional

class FiltroPagoForm(FlaskForm):
    curso = SelectField('Curso', choices=[], validators=[Optional()])
    nombre = StringField('Estudiante', validators=[Optional()])
    estado = SelectField('Estado', choices=[
        ('', 'Todos'),
        ('pagado', 'Pagado'),
        ('pendiente', 'Pendiente')
    ], validators=[Optional()])