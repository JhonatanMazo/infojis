from flask_wtf import FlaskForm
from wtforms import SelectField
from wtforms.validators import Optional

class FiltroInclusion(FlaskForm):
    curso = SelectField('Curso', choices=[], validators=[Optional()])