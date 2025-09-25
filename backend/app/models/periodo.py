from app import db


class Periodo(db.Model):
    __tablename__ = 'periodos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    fecha_inicio = db.Column(db.String(5), nullable=False) # Formato MM-DD
    fecha_fin = db.Column(db.String(5), nullable=False)   # Formato MM-DD
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    usuario = db.relationship('User', backref='periodos', lazy=True, foreign_keys=[id_usuario])
    anio_periodos = db.relationship('AnioPeriodo', back_populates='periodo', cascade='all, delete-orphan')
    
    def __init__(self, nombre, fecha_inicio, fecha_fin, id_usuario=None):
        self.nombre = nombre
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.id_usuario = id_usuario
    
    def __repr__(self):
        return f'<Periodo {self.nombre}>'

