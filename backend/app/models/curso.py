from app import db


class Curso(db.Model):
    __tablename__ = 'cursos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(20), default='activo')
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)
    
    usuario = db.relationship('User', backref='cursos', lazy=True, foreign_keys=[id_usuario])
    asignaciones = db.relationship('Asignacion', back_populates='curso', cascade='all, delete-orphan')
    matriculas = db.relationship('Matricula', back_populates='curso', cascade='all, delete-orphan')
    boletines = db.relationship('Boletin', back_populates='curso', cascade='all, delete-orphan')
    inclusiones = db.relationship('Inclusion', back_populates='curso', cascade='all, delete-orphan')
    pagos = db.relationship('Pago', back_populates='curso', cascade='all, delete-orphan')
    
    @property
    def activo(self):
        """Propiedad útil para lógica Python"""
        return self.estado == 'activo'

    
    def __repr__(self):
        return f'<Curso {self.nombre}>'
