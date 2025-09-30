from datetime import date
from app import db
from sqlalchemy import Enum, case, exc, and_, UniqueConstraint
from sqlalchemy.sql import func
from app.models.curso import Curso
import logging
from app.services.configuracion_service import get_active_config

logger = logging.getLogger(__name__)

class Matricula(db.Model):
    __tablename__ = 'matricula'
    
    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    genero = db.Column(Enum('femenino', 'masculino', name='genero_types'), nullable=False)
    documento = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('cursos.id', ondelete='CASCADE'), nullable=False)
    año_lectivo = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='activo')
    eliminado = db.Column(db.Boolean, default=False, nullable=False)
    fecha_matricula = db.Column(db.Date, nullable=False, default=date.today)
    foto = db.Column(db.String(255))
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fecha_transferencia = db.Column(db.DateTime, nullable=True)
    transferido_por = db.Column(db.String(100), nullable=True)
    observaciones_transferencia = db.Column(db.Text, nullable=True)
    curso_origen = db.Column(db.String(100), nullable=True)
    eliminado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_eliminacion = db.Column(db.DateTime, nullable=True)

    # Relaciones
    usuario = db.relationship('User', backref='matriculas', lazy=True, foreign_keys=[id_usuario])
    curso = db.relationship('Curso', back_populates='matriculas')
    asistencias = db.relationship('Asistencia', back_populates='matricula', cascade='all, delete-orphan')
    observaciones = db.relationship('Observacion', back_populates='matricula', cascade='all, delete-orphan')
    calificaciones = db.relationship('Calificacion', back_populates='matricula', cascade='all, delete-orphan')
    inclusiones = db.relationship('Inclusion', back_populates='matricula', cascade='all, delete-orphan')
    pagos = db.relationship('Pago', back_populates='matricula', cascade='all, delete-orphan', passive_deletes=True)
    boletines = db.relationship('Boletin', back_populates='matricula', cascade='all, delete-orphan')
    
    __table_args__ = (
        UniqueConstraint('documento', 'año_lectivo', name='uq_documento_anio'),
    )


    def __repr__(self):
        return f'<Matricula {self.nombres} {self.apellidos}>'

    @classmethod
    def get_by_active_year(cls, page=1, per_page=10, estado=None, curso_id=None):
        """Obtiene matrículas paginadas del año activo con filtros"""
        try:
            config = get_active_config()
            if not config:
                logger.warning("No hay configuración activa")
                return None

            query = cls.query.filter_by(año_lectivo=config['anio'])

            if estado:
                query = query.filter_by(estado=estado)
            if curso_id:
                query = query.filter_by(id_curso=curso_id)

            return query.order_by(
                cls.fecha_matricula.desc()
            ).paginate(page=page, per_page=per_page, error_out=False)

        except exc.SQLAlchemyError as e:
            logger.error(f"Error de BD al obtener matrículas: {str(e)}")
            raise

    @classmethod
    def contar_por_curso(cls, curso_id):
        """Cuenta matrículas activas en un curso para el año activo"""
        try:
            config = get_active_config()
            if not config:
                return 0

            return cls.query.filter(
                and_(
                    cls.id_curso == curso_id,
                    cls.año_lectivo == config['anio'],
                    cls.estado == 'activo'
                )
            ).count()

        except exc.SQLAlchemyError as e:
            logger.error(f"Error contando matrículas: {str(e)}")
            raise


    @classmethod
    def estadisticas_por_curso(cls):
        """Obtiene estadísticas de matrículas por curso"""
        try:
            config = get_active_config()
            if not config:
                return []

            return db.session.query(
                Curso.nombre,
                func.count(cls.id).label('total'),
                func.sum(case((cls.estado == 'activo', 1), else_=0)).label('activos'),
                func.sum(case((cls.estado == 'retirado', 1), else_=0)).label('retirados')
            ).join(Curso).filter(
                cls.año_lectivo == config['anio']
            ).group_by(Curso.nombre).all()

        except exc.SQLAlchemyError as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            raise

def on_curso_change(target, value, oldvalue, initiator):
    """Cuando el id_curso de una matrícula cambia, actualiza el id_curso en los boletines asociados."""
    if oldvalue != value and target.id is not None:
        for boletin in target.boletines:
            boletin.id_curso = value
    return value
db.event.listen(Matricula.id_curso, 'set', on_curso_change, retval=True)
