from datetime import datetime
from app import db
from sqlalchemy.orm import validates

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    anio = db.Column(db.Integer, nullable=False, unique=True)
    estado = db.Column(db.String(20), nullable=False, default='activo')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @validates('anio')
    def validate_anio(self, key, anio):
        """Valida que el año esté en un rango razonable"""
        if anio < 2000 or anio > 2100:
            raise ValueError("El año debe estar entre 2000 y 2100")
        return anio
    
    def __repr__(self):
        return f'<SystemConfig {self.anio} ({self.estado})>'
    
    @classmethod
    def get_active_config(cls):
        """Obtiene la configuración activa actual"""
        return cls.query.filter_by(estado='activo').first()
    
    @classmethod
    def set_active_config(cls, anio):
        """Establece una configuración como activa de forma atómica"""
        try:
            # Obtener la configuración a activar primero
            config = cls.query.filter_by(anio=anio).first()
            if not config:
                return None
                
            # Realizar ambas operaciones en la misma transacción
            db.session.execute(
                db.update(cls)
                .values(estado=db.case(
                    (cls.id == config.id, 'activo'),
                    else_='inactivo'
                ))
                .where(db.or_(cls.id == config.id, cls.estado == 'activo'))
            )
            
            config.updated_at = datetime.utcnow()
            db.session.commit()
            return config
        except Exception as e:
            db.session.rollback()
            raise e
    
    @classmethod
    def get_all_years(cls):
        """Obtiene todos los años configurados ordenados descendentemente"""
        return cls.query.order_by(cls.anio.desc()).all()
    
    @classmethod
    def get_by_year(cls, anio):
        """Obtiene la configuración para un año específico"""
        return cls.query.filter_by(anio=anio).first()
    
    def to_dict(self):
        """Convierte el objeto a diccionario"""
        return {
            'id': self.id,
            'anio': self.anio,
            'estado': self.estado,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        
        
# NUEVO MODELO GLOBAL PARA RECTOR
class RectorConfig(db.Model):
    __tablename__ = 'rector_config'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=True)
    identidad = db.Column(db.String(40), nullable=True)
    firma_url = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'identidad': self.identidad,
            'firma_url': self.firma_url,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }        