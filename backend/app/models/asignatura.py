from app import db


class Asignatura(db.Model):
    __tablename__ = 'asignaturas'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(20), nullable=False, default='activo')
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    usuario = db.relationship('User', backref='asignaturas', lazy=True, foreign_keys=[id_usuario])
    asignaciones = db.relationship('Asignacion', back_populates='asignatura', cascade='all, delete-orphan')
    
    def __init__(self, nombre, descripcion=None, estado='activo', id_usuario=None):
        self.nombre = nombre
        self.descripcion = descripcion
        self.estado = estado
        self.id_usuario = id_usuario
    
    def __repr__(self):
        return f'<Asignatura {self.nombre}>'