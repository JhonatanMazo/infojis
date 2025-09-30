import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from datetime import datetime
from app import db
from app.models.configuracion import RectorConfig, SystemConfig
from app.models import Periodo, AnioPeriodo
from app.services.configuracion_service import reload_active_config, clear_config_cache
import logging
from app.utils.decorators import admin_required
from app.utils.file_uploads import remove_rector_firma, upload_rector_firma
from app.services.configuracion_service import get_active_config as get_active_system_config_dict

config_bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')
logger = logging.getLogger(__name__)

@config_bp.route('/', methods=['GET'])
@admin_required
def index():
    config_activa = get_active_system_config_dict() # Get the cached dictionary
    todos_anios = SystemConfig.query.order_by(SystemConfig.anio.desc()).all()
    # Change here: filter periodos to only those not eliminado
    periodos = Periodo.query.filter_by(eliminado=False).order_by(Periodo.nombre).all()
    rector_config = RectorConfig.query.first()

    return render_template(
        'views/configuracion.html',
        config_activa=config_activa,
        todos_anios=todos_anios,
        periodos=periodos,
        current_year=datetime.now().year,
        rector_config=rector_config
    )


@config_bp.route('/cambiar-anio', methods=['POST'])
@admin_required
def cambiar_anio():
    try:
        anio = int(request.form.get('anio'))
        periodo_id = int(request.form.get('periodo_id'))

        logger.debug(f"Attempting to change year to: {anio}, period_id: {periodo_id}")

        # Activar el año lectivo
        config = SystemConfig.set_active_config(anio)
        if not config:
            flash('El año seleccionado no existe', 'danger')
            return redirect(url_for('configuracion.index'))

        # Get the currently active AnioPeriodo before any changes
        current_active_anio_periodo = AnioPeriodo.query.filter_by(estado='activo').first()
        if current_active_anio_periodo:
            logger.debug(f"Currently active AnioPeriodo: {current_active_anio_periodo.anio_lectivo}-{current_active_anio_periodo.periodo.nombre}")
            # If the currently active AnioPeriodo is from a different year, deactivate it
            if current_active_anio_periodo.anio_lectivo != anio:
                current_active_anio_periodo.estado = 'inactivo'
                logger.debug(f"Deactivated previous active AnioPeriodo: {current_active_anio_periodo.anio_lectivo}-{current_active_anio_periodo.periodo.nombre}")

        # Log current active AnioPeriodo entries before deactivation
        active_anio_periodos_before = AnioPeriodo.query.filter_by(estado='activo').all()
        logger.debug(f"Active AnioPeriodos BEFORE deactivation: {[f'{ap.anio_lectivo}-{ap.periodo.nombre}' for ap in active_anio_periodos_before]}")

        # Desactivar todos los AnioPeriodo para ese año
        AnioPeriodo.query.filter_by(anio_lectivo=anio).update({'estado': 'inactivo'})
        logger.debug(f"Deactivated AnioPeriodos for year {anio}")

        # Desactivar AnioPeriodo con el mismo periodo_id pero diferente anio_lectivo
        AnioPeriodo.query.filter(
            AnioPeriodo.periodo_id == periodo_id,
            AnioPeriodo.anio_lectivo != anio
        ).update({'estado': 'inactivo'})
        logger.debug(f"Deactivated AnioPeriodos with periodo_id {periodo_id} for other years")

        # Activar el AnioPeriodo seleccionado
        anio_periodo_seleccionado = AnioPeriodo.query.filter_by(anio_lectivo=anio, periodo_id=periodo_id).first()
        if anio_periodo_seleccionado:
            anio_periodo_seleccionado.estado = 'activo'
            flash(f'Año {anio} activado con el período {anio_periodo_seleccionado.periodo.nombre} como activo.', 'success')
        else:
            db.session.rollback()
            flash('El período seleccionado no es válido para este año.', 'danger')
            return redirect(url_for('configuracion.index'))

        db.session.commit() # Consolidate commit here

        # Log current active AnioPeriodo entries after commit
        active_anio_periodos_after = AnioPeriodo.query.filter_by(estado='activo').all()
        logger.debug(f"Active AnioPeriodos AFTER commit: {[f'{ap.anio_lectivo}-{ap.periodo.nombre}' for ap in active_anio_periodos_after]}")

        # Limpiar caches después de confirmar la transacción
        clear_config_cache()
        reload_active_config()
        
        return redirect(url_for('configuracion.index', anio_cambiado=anio))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al cambiar año: {str(e)}", exc_info=True)
        flash(f'Error al cambiar año: {str(e)}', 'danger')
        return redirect(url_for('configuracion.index'))
        
        
@config_bp.route('/crear-anio', methods=['POST'])
@admin_required
def crear_anio():
    try:
        nuevo_anio = int(request.form.get('nuevo_anio'))
        current_year = datetime.now().year
        if nuevo_anio < current_year - 1 or nuevo_anio > current_year + 1:
            flash('El año debe estar entre el año anterior y el año siguiente. Del año actual', 'danger')
            return redirect(url_for('configuracion.index'))
            
        if SystemConfig.query.filter_by(anio=nuevo_anio).first():
            flash('Este año ya está configurado', 'warning')
            return redirect(url_for('configuracion.index'))

        nueva_config = SystemConfig(
            anio=nuevo_anio,
            estado='inactivo'
        )
        
        db.session.add(nueva_config)
        db.session.commit()
        
        # Create AnioPeriodo entries for all existing Periodos for the new year
        periodos_existentes = Periodo.query.all()
        for periodo in periodos_existentes:
            # Use dates from the Periodo object
            nuevo_anio_periodo = AnioPeriodo(
                anio_lectivo=nuevo_anio,
                periodo_id=periodo.id,
                fecha_inicio=periodo.fecha_inicio,
                fecha_fin=periodo.fecha_fin,
                estado="inactivo"       # Initially inactive
            )
            db.session.add(nuevo_anio_periodo)
        
        db.session.commit() # Commit the new AnioPeriodo entries
        
        logger.info(f"Nuevo año lectivo creado: {nuevo_anio} por usuario {current_user.id}")
        flash(f'Año lectivo {nuevo_anio} creado correctamente y períodos asociados inicializados.', 'success')
        
    except ValueError:
        flash('Datos inválidos', 'danger')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al crear año: {str(e)}", exc_info=True)
        flash(f'Error al crear año: {str(e)}', 'danger')
        
    return redirect(url_for('configuracion.index'))
        
        






@config_bp.route('/actualizar-rector', methods=['POST'])
@admin_required
def actualizar_rector():
    nombre = request.form.get('rector_nombre')
    identidad = request.form.get('rector_identidad')
    firma_file = request.files.get('rector_firma')

    config = RectorConfig.query.first()
    if not config:
        config = RectorConfig()
        db.session.add(config)

    config.nombre = nombre
    config.identidad = identidad

    # Si se sube una imagen
    if firma_file and firma_file.filename:
        # Remover la firma anterior si existe
        if config.firma_url:
            # Extrae solo el nombre del archivo
            old_filename = os.path.basename(config.firma_url)
            remove_rector_firma(old_filename)

        firma_url = upload_rector_firma(firma_file)
        if firma_url:
            config.firma_url = '/' + firma_url.replace('\\', '/')

    db.session.commit()
    flash('Datos del rector actualizados correctamente', 'success')
    return redirect(url_for('configuracion.index'))
