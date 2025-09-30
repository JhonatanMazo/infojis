from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, HiddenField
from wtforms.validators import DataRequired, Optional
from datetime import date

class FiltroAsistenciasForm(FlaskForm):
    curso = SelectField('Curso', coerce=int, validators=[Optional()])
    asignatura = SelectField('Asignatura', coerce=int, validators=[Optional()])
    fecha = DateField('Fecha', default=date.today, validators=[Optional()])

class AsistenciaForm(FlaskForm):
    matricula_id = HiddenField('ID Matrícula', validators=[DataRequired()])
    estado = HiddenField('Estado', validators=[DataRequired()])
    observaciones = HiddenField('Observaciones', validators=[Optional()])