from .actividades import actividades_bp
from .main import main_bp
from .auth import auth_bp
from .dashboard import dashboard_bp
from .usuarios import usuarios_bp
from .perfil import perfil_bp
from .periodos import periodos_bp
from .cursos import cursos_bp
from .asignaturas import asignaturas_bp
from .matricula import matricula_bp
from .inclusion import inclusion_bp
from .asignacion import asignacion_bp
from .asistencias import asistencias_bp
from .calificaciones import calificacion_bp
from .pagos import pago_bp
from .observaciones import observaciones_bp
from .academico import academico_bp
from .posiciones  import posiciones_bp
from .libro_final import libro_final_bp
from .transferir import transferencia_bp
from .exportar import exportar_bp
from .documentos import documentos_bp
from .estadisticas import estadisticas_bp
from .configuracion import config_bp
from .reciclaje import reciclaje_bp
from .actividades import actividades_bp
from .boletines import boletines_bp





def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(periodos_bp)
    app.register_blueprint(cursos_bp)
    app.register_blueprint(asignaturas_bp)
    app.register_blueprint(matricula_bp)
    app.register_blueprint(inclusion_bp)
    app.register_blueprint(asignacion_bp)
    app.register_blueprint(asistencias_bp)
    app.register_blueprint(calificacion_bp)
    app.register_blueprint(pago_bp)
    app.register_blueprint(observaciones_bp)
    app.register_blueprint(academico_bp)
    app.register_blueprint(posiciones_bp)
    app.register_blueprint(libro_final_bp)
    app.register_blueprint(transferencia_bp)
    app.register_blueprint(exportar_bp)
    app.register_blueprint(documentos_bp)
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(actividades_bp)
    app.register_blueprint(reciclaje_bp)
    app.register_blueprint(boletines_bp)
    