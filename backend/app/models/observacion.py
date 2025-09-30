from app import db
from datetime import datetime

class Observacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)  
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id', ondelete='CASCADE'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo = db.Column(db.Enum('académica', 'asistencia', 'disciplinaria'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    detalles = db.Column(db.String(255))  
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    # Relaciones
    matricula = db.relationship('Matricula', back_populates='observaciones')
    curso = db.relationship('Curso', backref=db.backref('observaciones', lazy=True))
    usuario = db.relationship('User', backref='observaciones', lazy=True, foreign_keys=[id_usuario])
