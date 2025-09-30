from datetime import datetime
from app import db


class Asistencia(db.Model):
    __tablename__ = 'asistencias'
    
    id = db.Column(db.Integer, primary_key=True)
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id', ondelete='CASCADE'), nullable=False)
    id_asignacion = db.Column(db.Integer, db.ForeignKey('asignaciones.id'), nullable=False) 
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    estado = db.Column(db.String(20), nullable=False, default='asistencia')
    observaciones = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    actualizado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    # Relaciones
    matricula = db.relationship('Matricula', back_populates='asistencias')
    asignacion = db.relationship('Asignacion', back_populates='asistencias')
    creador = db.relationship('User', foreign_keys=[creado_por])
    actualizador = db.relationship('User', foreign_keys=[actualizado_por])
    
    @classmethod
    def registrar_asistencia(cls, id_matricula, id_asignacion, fecha, estado, observaciones=None, usuario_id=None):
        """Registra o actualiza una asistencia"""
        asistencia = cls.query.filter_by(
            id_matricula=id_matricula,
            id_asignacion=id_asignacion,
            fecha=fecha
        ).first()

        if asistencia:
            asistencia.estado = estado
            asistencia.observaciones = observaciones
            asistencia.actualizado_por = usuario_id
        else:
            asistencia = cls(
                id_matricula=id_matricula,
                id_asignacion=id_asignacion,
                fecha=fecha,
                estado=estado,
                observaciones=observaciones,
                creado_por=usuario_id
            )
            db.session.add(asistencia)

        return asistencia