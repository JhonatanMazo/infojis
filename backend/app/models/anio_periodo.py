from app import db

class AnioPeriodo(db.Model):
    __tablename__ = 'anio_periodo'
    
    id = db.Column(db.Integer, primary_key=True)
    anio_lectivo = db.Column(db.Integer, nullable=False)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodos.id'), nullable=False)
    fecha_inicio = db.Column(db.String(5), nullable=False) # Formato MM-DD
    fecha_fin = db.Column(db.String(5), nullable=False)   # Formato MM-DD
    estado = db.Column(db.String(20), nullable=False, default='inactivo')
    
    periodo = db.relationship('Periodo', back_populates='anio_periodos')

    def __init__(self, anio_lectivo, periodo_id, fecha_inicio, fecha_fin, estado='inactivo'):
        self.anio_lectivo = anio_lectivo
        self.periodo_id = periodo_id
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.estado = estado

    def __repr__(self):
        return f'<AnioPeriodo {self.anio_lectivo} - {self.periodo.nombre}>'
