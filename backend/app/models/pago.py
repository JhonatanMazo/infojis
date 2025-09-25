from app import db
from datetime import datetime
from sqlalchemy import Enum


class Pago(db.Model):
    __tablename__ = 'pagos'

    id = db.Column(db.Integer, primary_key=True)
    foto = db.Column(db.String(255))
    eliminado = db.Column(db.Boolean, default=False, nullable=False)

    
    id_matricula = db.Column(db.Integer, db.ForeignKey('matricula.id', ondelete='CASCADE'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False)
    

    concepto = db.Column(
        Enum('Matricula', 'Mensualidad', 'Derecho a grado', name='concepto_enum'),
        nullable=False
    )

    monto = db.Column(db.Integer, nullable=False)

    metodo_pago = db.Column(
        Enum('efectivo', 'transferencia', 'tarjeta', 'consignacion', name='metodo_pago_enum'),
        nullable=False
    )

    fecha_pago = db.Column(db.Date, nullable=False)

    estado = db.Column(
        Enum('pendiente', 'pagado', name='estado_pago_enum'),
        default='pendiente'
    )

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    # Relaciones (opcional si quieres acceder desde el objeto)
    matricula = db.relationship('Matricula', back_populates='pagos')
    curso = db.relationship('Curso', back_populates='pagos')
    usuario = db.relationship('User', backref='pagos', lazy=True, foreign_keys=[id_usuario])  # suponiendo modelo User