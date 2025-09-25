from app import db
from datetime import datetime

class Actividad(db.Model):
    __tablename__ = 'actividades'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    detalle = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    id_asignacion = db.Column(db.Integer, db.ForeignKey('asignaciones.id'), nullable=True)

    asignacion = db.relationship('Asignacion', back_populates='actividades')

    def __repr__(self):
        return f'<Actividad {self.titulo}>'