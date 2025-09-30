from flask_wtf import FlaskForm
from wtforms import SelectField
from wtforms.validators import Optional

class FiltroMatriculaForm(FlaskForm):
    estado = SelectField('Estado', choices=[
        ('', 'Todos'),
        ('activo', 'Activo'),
        ('retirado', 'Retirado')
    ], validators=[Optional()])
    
    curso = SelectField('Curso', coerce=int, validators=[Optional()])