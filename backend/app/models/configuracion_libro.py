from app import db
from datetime import datetime
from app.services.configuracion_service import get_active_year

class ConfiguracionLibro(db.Model):
    __tablename__ = 'configuracion_libro'
    
    id = db.Column(db.Integer, primary_key=True)
    nivel_aprobacion = db.Column(db.Float, nullable=False, default=70.0)
    nota_superior = db.Column(db.Float, nullable=False, default=4.5)
    nota_alto = db.Column(db.Float, nullable=False, default=4.0)
    nota_basico = db.Column(db.Float, nullable=False, default=3.0)
    año_lectivo_actual = db.Column(db.Integer, nullable=False)
    formato_exportacion = db.Column(db.String(20), nullable=False, default='excel')
    incluir_firma = db.Column(db.Boolean, nullable=False, default=True)
    incluir_sello = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, onupdate=datetime.utcnow)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True)

    # Relaciones
    usuario = db.relationship('User', backref='configuraciones_libro', lazy=True)
    
    def __init__(self, nivel_aprobacion=70.0, año_lectivo_actual=None, formato_exportacion='excel', incluir_firma=True, incluir_sello=True, id_usuario=None, nota_superior=4.5, nota_alto=4.0, nota_basico=3.0):
        self.nivel_aprobacion = nivel_aprobacion
        self.nota_superior = nota_superior
        self.nota_alto = nota_alto
        self.nota_basico = nota_basico
        self.año_lectivo_actual = año_lectivo_actual or datetime.now().year
        self.formato_exportacion = formato_exportacion
        self.incluir_firma = incluir_firma
        self.incluir_sello = incluir_sello
        self.id_usuario = id_usuario
    
    def to_dict(self):
        return {
            'id': self.id,
            'nota_superior': self.nota_superior,
            'nota_alto': self.nota_alto,
            'nota_basico': self.nota_basico,
            'año_lectivo_actual': self.año_lectivo_actual,
            'formato_exportacion': self.formato_exportacion,
            'incluir_firma': self.incluir_firma,
            'incluir_sello': self.incluir_sello,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None
        }
    
    @classmethod
    def obtener_configuracion_actual(cls):
        """Obtener la configuración para el año lectivo activo."""
        active_year = get_active_year()
        if not active_year:
            active_year = datetime.now().year

        config = cls.query.filter_by(año_lectivo_actual=active_year).first()
        if not config:
            # If no config for active year, create one with default values.
            config = cls(
                año_lectivo_actual=active_year,
                nota_superior=4.5,
                nota_alto=4.0,
                nota_basico=3.0,
                formato_exportacion='excel',
                incluir_firma=True,
                incluir_sello=True
            )
            db.session.add(config)
            db.session.commit()
        return config
    
    def __repr__(self):
        return f'<ConfiguracionLibro {self.año_lectivo_actual}>' 