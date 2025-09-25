from datetime import datetime
from app import db

class Inclusion(db.Model):
    __tablename__ = 'inclusiones'

    id = db.Column(db.Integer, primary_key=True)    
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    tipo_necesidad = db.Column(db.String(100), nullable=False)
    plan_apollo = db.Column(db.Text, nullable=True)
    fecha_ingreso = db.Column(db.Date, default=datetime.utcnow)
    detalles = db.Column(db.String(300), nullable=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='activo', nullable=False)
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    # Relaciones
    matricula = db.relationship('Matricula', back_populates='inclusiones')
    curso = db.relationship('Curso', back_populates='inclusiones')
    usuario = db.relationship('User', backref='inclusiones', lazy=True, foreign_keys=[id_usuario])

    def __repr__(self):
        return f'<Inclusion {self.id} - Usuario {self.id_usuario}>'