from app import db
from datetime import datetime


class Asignacion(db.Model):
    __tablename__ = 'asignaciones'

    id = db.Column(db.Integer, primary_key=True)
    id_docente = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    id_asignatura = db.Column(db.Integer, db.ForeignKey('asignaturas.id', ondelete='CASCADE'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    id_periodo = db.Column(db.Integer, db.ForeignKey('periodos.id', ondelete='CASCADE'), nullable=True)
    anio_lectivo = db.Column(db.Integer, nullable=False)
    horas_impartidas = db.Column(db.Integer, nullable=True)
    observaciones = db.Column(db.Text)
    fecha_asignacion = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(10), nullable=False, default='activo')
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    docente = db.relationship('User', back_populates='asignaciones', foreign_keys=[id_docente])
    asignatura = db.relationship('Asignatura', back_populates='asignaciones')
    curso = db.relationship('Curso', back_populates='asignaciones')
    periodo = db.relationship('Periodo', backref='asignaciones')
    calificaciones = db.relationship('Calificacion', back_populates='asignacion', cascade='all, delete-orphan')
    asistencias = db.relationship('Asistencia', back_populates='asignacion', cascade='all, delete-orphan')
    actividades = db.relationship('Actividad', back_populates='asignacion', cascade='all, delete-orphan')