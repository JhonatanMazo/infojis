from app import db
from datetime import datetime


class Calificacion(db.Model):
    __tablename__ = 'calificacion'
    
    id = db.Column(db.Integer, primary_key=True)
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id', ondelete='CASCADE'), nullable=False)
    id_asignacion = db.Column(db.Integer, db.ForeignKey('asignaciones.id', ondelete='CASCADE'), nullable=False)
    id_periodo = db.Column(db.Integer, db.ForeignKey('periodos.id', ondelete='CASCADE'), nullable=False)
    fecha_calificacion = db.Column(db.Date, nullable=False)
    nota = db.Column(db.Float, nullable=True)
    observacion = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, onupdate=datetime.utcnow)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    actualizado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # Relaciones
    matricula = db.relationship('Matricula', back_populates='calificaciones')
    asignacion = db.relationship('Asignacion', back_populates='calificaciones')
    creador = db.relationship('User', foreign_keys=[creado_por], backref='calificaciones_creadas')
    editor = db.relationship('User', foreign_keys=[actualizado_por], backref='calificaciones_actualizadas')
    
    def __repr__(self):
        return f'<Calificacion {self.id}>'