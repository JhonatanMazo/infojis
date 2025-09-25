from datetime import datetime
from app import db


class Informe(db.Model):
    __tablename__ = 'informes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(20), nullable=False) 
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=True)
    id_periodo = db.Column(db.Integer, db.ForeignKey('periodos.id', ondelete='CASCADE'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_generacion = db.Column(db.DateTime, default=datetime.utcnow)
    ruta_archivo = db.Column(db.String(255), nullable=False)
    campos_incluidos = db.Column(db.JSON) 
    
    # Relaciones
    curso = db.relationship('Curso', backref='informes')
    periodo = db.relationship('Periodo', backref='informes')
    usuario = db.relationship('User', backref='informes')
    
    def get_tipo_display(self):
        tipos = {
            'desempeno': 'Desempeño Académico',
            'asistencia': 'Asistencia',
            'conducta': 'Conducta'
        }
        return tipos.get(self.tipo, self.tipo)
    
    def get_badge_class(self):
        clases = {
            'desempeno': 'bg-primary',
            'asistencia': 'bg-success',
            'conducta': 'bg-warning text-dark'
        }
        return clases.get(self.tipo, 'bg-secondary')