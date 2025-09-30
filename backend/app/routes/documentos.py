from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response
from flask_login import current_user
from sqlalchemy import func
from app import db
from app.models import Matricula, Curso, Asignacion, AnioPeriodo
from app.models.calificacion import Calificacion as CalificacionModel
from app.models.configuracion_libro import ConfiguracionLibro
from app.models.configuracion import RectorConfig
from app.services.configuracion_service import get_active_config
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
import os
from datetime import datetime
from io import BytesIO
from app.utils.decorators import roles_required
import zipfile

documentos_bp = Blueprint('documentos', __name__, url_prefix='/documentos')

# Tipos de documentos permitidos
TIPOS_DOCUMENTOS = ['certificados', 'constancias']

# Función para convertir números a texto en español
def numero_a_texto(numero):
    unidades = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']
    especiales = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve']
    decenas = ['', 'diez', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa']
    
    if 1 <= numero <= 9:
        return unidades[numero]
    elif 10 <= numero <= 19:
        return especiales[numero - 10]
    elif 20 <= numero <= 29:
        if numero == 20:
            return 'veinte'
        else:
            return 'veinti' + unidades[numero - 20]
    elif 30 <= numero <= 99:
        decena = numero // 10
        unidad = numero % 10
        if unidad == 0:
            return decenas[decena]
        else:
            return decenas[decena] + ' y ' + unidades[unidad]
    else:
        return str(numero)
    
    
def calcular_promedio_periodo(matricula_id, periodo_id, anio_lectivo):
    """Calcula el promedio de un estudiante en un período específico - Mismo método que libro_final"""
    try:
        # Obtener las fechas del período (igual que en libro_final.py)
        anio_periodo = AnioPeriodo.query.filter_by(
            anio_lectivo=anio_lectivo, 
            periodo_id=periodo_id
        ).first()
        
        if not anio_periodo or not anio_periodo.fecha_inicio or not anio_periodo.fecha_fin:
            return 0.0
            
        fecha_inicio = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_inicio}", "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(f"{anio_lectivo}-{anio_periodo.fecha_fin}", "%Y-%m-%d").date()

        # USAR EXACTAMENTE EL MISMO MÉTODO QUE LIBRO_FINAL
        # Crear subconsulta igual que en _obtener_datos_libro_final
        subquery = db.session.query(
            CalificacionModel.id_matricula,
            func.avg(CalificacionModel.nota).label('promedio_periodo')
        ).join(Asignacion, CalificacionModel.id_asignacion == Asignacion.id).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            CalificacionModel.fecha_calificacion.between(fecha_inicio, fecha_fin),
            CalificacionModel.id_matricula == matricula_id  # Filtrar por el estudiante específico
        ).group_by(CalificacionModel.id_matricula).subquery()

        # Obtener el promedio directamente
        promedio = db.session.query(
            subquery.c.promedio_periodo
        ).filter(
            subquery.c.id_matricula == matricula_id
        ).scalar()
        
        return promedio if promedio is not None else 0.0
        
    except Exception as e:
        print(f"Error al calcular promedio del período: {str(e)}")
        return 0.0
    
def verificar_aprobacion_estudiante(matricula_id):
    """Usa el mismo método directo que libro_final.py"""
    try:
        config = ConfiguracionLibro.obtener_configuracion_actual()
        config_general = get_active_config()
        anio_lectivo = config_general['anio'] if config_general and 'anio' in config_general else None
        
        if not anio_lectivo:
            return False, 0.0
        
        matricula = Matricula.query.get(matricula_id)
        if not matricula or matricula.año_lectivo != anio_lectivo:
            return False, 0.0

        # Obtener TODOS los datos como lo hace libro_final
        periodo_id = config_general.get('periodo_id')
        if not periodo_id:
            return False, 0.0
            
        # Usar la función de libro_final directamente
        from app.routes.libro_final import _obtener_datos_libro_final
        datos_estudiantes = _obtener_datos_libro_final(matricula.id_curso, anio_lectivo)
        
        # Buscar el estudiante específico
        estudiante_data = next((e for e in datos_estudiantes if e['id'] == matricula_id), None)
        
        if not estudiante_data:
            return False, 0.0
            
        promedio_final = estudiante_data['promedio_periodo']
        aprobado = promedio_final >= config.nota_basico if promedio_final is not None else False
        
        return aprobado, round(promedio_final, 1) if promedio_final is not None else 0.0
        
    except Exception as e:
        print(f"Error al verificar aprobación: {str(e)}")
        return False, 0.0

@documentos_bp.context_processor
def utility_processor():
    def verificar_aprobacion_estudiante_template(matricula_id):
        aprobado, promedio = verificar_aprobacion_estudiante(matricula_id)
        return aprobado, promedio
    return dict(verificar_aprobacion_estudiante=verificar_aprobacion_estudiante_template)


@documentos_bp.route('/', methods=['GET'])
@roles_required('admin', 'docente')
def listar_documentos():
    # Obtener parámetros de filtro
    curso_id = request.args.get('curso', type=int)
    tipo_documento = request.args.get('tipo', default='', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = 10

    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    
    # Obtener cursos disponibles según el rol y año lectivo activo
    if current_user.is_admin():
        # Para admin: todos los cursos con asignaciones activas en el año lectivo actual
        cursos_ids = db.session.query(Asignacion.id_curso).filter(
            Asignacion.anio_lectivo == anio_lectivo,
            Asignacion.estado == 'activo'
        ).distinct().all()
        cursos_ids = [c[0] for c in cursos_ids]
        cursos = Curso.query.filter(Curso.id.in_(cursos_ids), Curso.estado == 'activo').order_by(Curso.nombre).all() if cursos_ids else []
    else:
        # Para docente: solo los cursos asignados en el año lectivo activo
        cursos = Curso.query.join(Asignacion).filter(
            Asignacion.id_docente == current_user.id,
            Asignacion.estado == 'activo',
            Asignacion.anio_lectivo == anio_lectivo
        ).distinct().all()

    query = Matricula.query.filter_by(estado='activo')
    if anio_lectivo:
        query = query.filter(Matricula.año_lectivo == anio_lectivo)

    # Si es docente, filtrar solo las matrículas de sus cursos asignados
    if not current_user.is_admin():
        cursos_asignados_ids = [c.id for c in cursos]
        query = query.filter(Matricula.id_curso.in_(cursos_asignados_ids))

    if curso_id:
        query = query.filter_by(id_curso=curso_id)

    matriculas = query.order_by(Matricula.apellidos, Matricula.nombres).paginate(page=page, per_page=per_page, error_out=False)
    
    active_config = get_active_config()
    if not active_config:
        flash('No hay un año lectivo configurado como activo', 'warning')
        return redirect(url_for('configuracion.index'))
    anio_lectivo = active_config['anio']

    return render_template('views/documentos.html', 
                         matriculas=matriculas,
                         cursos=cursos,
                         curso_seleccionado=curso_id,
                         tipo_documento=tipo_documento,
                         ConfiguracionLibro=ConfiguracionLibro)


@documentos_bp.route('/generar/<int:matricula_id>/<tipo>', methods=['GET'])
@roles_required('admin', 'docente')
def generar_documento(matricula_id, tipo):
    if tipo not in TIPOS_DOCUMENTOS:
        flash('Tipo de documento no válido', 'danger')
        return redirect(url_for('documentos.listar_documentos'))

    matricula = Matricula.query.get_or_404(matricula_id)
    
    # Verificar que el docente tiene acceso a este curso
    if not current_user.is_admin():
        config = get_active_config()
        anio_lectivo = config['anio'] if config and 'anio' in config else None
        
        asignacion = Asignacion.query.filter_by(
            id_curso=matricula.id_curso,
            id_docente=current_user.id,
            estado='activo',
            anio_lectivo=anio_lectivo
        ).first()
        
        if not asignacion:
            flash('No tiene permisos para generar documentos de este curso', 'danger')
            return redirect(url_for('documentos.listar_documentos'))
    
    # Para certificados, verificar aprobación primero
    if tipo == 'certificados':
        # Verificar si el estudiante está aprobado
        aprobado, promedio_final = verificar_aprobacion_estudiante(matricula_id)
        
        if not aprobado:
            flash(f'No se puede generar certificado. El estudiante {matricula.nombres} {matricula.apellidos} no ha aprobado el año lectivo. Promedio: {promedio_final}', 'danger')
            return redirect(url_for('documentos.listar_documentos',
                                  curso=request.args.get('curso'),
                                  tipo=request.args.get('tipo'),
                                  page=request.args.get('page')))
        
        return generar_certificado(matricula, promedio_final)
    else:
        # Para constancias, no se necesita verificación de aprobación
        return generar_constancia(matricula)
    
    
def _obtener_datos_rector():
    config = RectorConfig.query.first()
    if config:
        return config.nombre or '___________________', config.identidad or 'N/A', config.firma_url or None
    return '', '', None


def generar_constancia(matricula):
    """Genera constancia de matrícula con el diseño actual"""
     # Obtener datos del rector desde la configuración activa
    rector_nombre, rector_identidad, rector_firma_url = _obtener_datos_rector()
    # Crear PDF con diseño decorado y profesional
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Configurar márgenes
    margin_left = 25 * mm
    margin_right = width - (25 * mm)
    
    # Colores elegantes
    color_primary = HexColor("#2C3E50")  # Azul oscuro elegante
    
    # Fondo con textura sutil
    c.setFillColor(HexColor("#F8F9FA"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Marco decorativo con esquinas ornamentadas
    c.setStrokeColor(color_primary)
    c.setLineWidth(0.5)
    c.roundRect(10*mm, 10*mm, width-20*mm, height-20*mm, 5*mm, stroke=1, fill=0) 
    
    # Logo centrado en la parte superior
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        logo_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
        
        if os.path.exists(logo_path):
            c.drawImage(logo_path, width/2-20*mm, height-50*mm, width=40*mm, height=35*mm, mask='auto', preserveAspectRatio=True)
    except Exception as e:
        print(f"Error al cargar el logo: {str(e)}")
    
    # Título del documento con estilo elegante
    titulo = "CONSTANCIA DE MATRÍCULA"
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, height-60*mm, titulo)
    
    # Ajustar posición inicial para centrar mejor el contenido
    current_y = height - 75*mm
    
    # Información de la institución con estilo mejorado
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "JARDIN INFANTIL SONRISAS")
    current_y -= 8*mm
    
    c.setFont("Helvetica-Oblique", 11)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "“Aprendiendo y sonriendo”")
    current_y -= 8*mm
    
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, "Código DANE N° 320001800766")
    current_y -= 8*mm
    
    c.drawCentredString(width/2, current_y, "Aprobado según resolución N° 000959 del 25 de Noviembre de 2024")
    current_y -= 20*mm
    
    # Texto principal con fondo resaltado
    texto_constancia = "LA SUSCRITA RECTORA HACE CONSTAR QUE"
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, texto_constancia)
    current_y -= 20*mm
    
    # Información del estudiante
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    hoy = datetime.now()
    
    # Convertir día a texto
    dia_texto = numero_a_texto(hoy.day)
    fecha_formateada = f"{dia_texto} [ {hoy.day:02d} ] días del mes de {meses[hoy.month-1]} del año {hoy.year}"
    
    texto_estudiante = f"El estudiante {matricula.nombres} {matricula.apellidos} identificado/a con "
    texto_estudiante += f"Registro Civil N° {matricula.documento}, se encuentra matriculado en nuestra institución "
    texto_estudiante += f"para el año escolar {matricula.año_lectivo} cursando el grado {matricula.curso.nombre}."
    
    # Dividir texto en líneas
    max_width = width - 2 * margin_left
    lines = []
    words = texto_estudiante.split()
    line = ""
    
    for word in words:
        test_line = f"{line} {word}" if line else word
        if c.stringWidth(test_line, "Helvetica", 11) <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    
    if line:
        lines.append(line)
    
    for line in lines:
        c.setFont("Helvetica", 11)
        c.setFillColor(black)
        c.drawString(margin_left, current_y, line)
        current_y -= 7*mm
    
    current_y -= 10*mm
    
    # Fecha y lugar
    dia_texto = numero_a_texto(hoy.day)
    fecha_formateada = f"Se expide en Valledupar, a los {dia_texto} ({hoy.day:02d}) días del mes de {meses[hoy.month-1]} de {hoy.year}"
    
       # Sección de firma con diseño mejorado
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawCentredString(width/2, current_y, fecha_formateada)
    current_y -= 40*mm  # Más espacio antes de la firma
    
    # Firma digital (imagen)
    if rector_firma_url:
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            firma_path = os.path.join(base_dir, 'frontend', 'static', rector_firma_url.lstrip('/static/'))
            if os.path.exists(firma_path):
                # Especificar mask='auto' para manejar transparencia
                c.drawImage(firma_path, width/2-25*mm, current_y-5*mm, width=50*mm, height=20*mm, mask='auto', preserveAspectRatio=True)
                current_y -= 5*mm
            else:
                print(f"Firma no encontrada en: {firma_path}")
        except Exception as e:
            print(f"Error al cargar la firma: {str(e)}")
    
    # Línea de firma DEBAJO de la imagen
    c.setStrokeColor(color_primary)
    c.setLineWidth(0.5)
    c.line(width/2-50*mm, current_y, width/2+50*mm, current_y)
    current_y -= 10*mm  # Espacio después de la línea

    # Información del rector DEBAJO de la línea
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, rector_nombre)
    current_y -= 6*mm

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, f"C.C {rector_identidad}")
    current_y -= 6*mm

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width/2, current_y, "Rector(a)")
    current_y -= 20*mm
    
    # Información de contacto sin recuadro
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "CONTACTO")
    current_y -= 5*mm
    
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, "Urbanización Luis Carlos Galán Mz E casa 9")
    current_y -= 5*mm
    c.drawCentredString(width/2, current_y, "jardininfantilsonrisas2023@gmail.com")
    current_y -= 5*mm
    c.drawCentredString(width/2, current_y, "300 149 8933")
  
    c.save()
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=constancia_{matricula.nombres}_{matricula.apellidos}.pdf'
    return response

def generar_certificado(matricula, promedio_final):
    """Genera certificado de estudios con formato profesional"""
    
     # Obtener datos del rector desde la configuración activa
    rector_nombre, rector_identidad, rector_firma_url = _obtener_datos_rector()
            
    # Crear PDF con diseño decorado y profesional
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4) # Corregido: usar el buffer local
    width, height = A4
    
    # Configurar márgenes
    margin_left = 25 * mm
    margin_right = width - (25 * mm)
    
    # Colores elegantes
    color_primary = HexColor("#2C3E50")  # Azul oscuro elegante
    
    # Fondo con textura sutil
    c.setFillColor(HexColor("#F8F9FA"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Marco decorativo con esquinas ornamentadas
    c.setStrokeColor(color_primary)
    c.setLineWidth(0.5)
    c.roundRect(10*mm, 10*mm, width-20*mm, height-20*mm, 5*mm, stroke=1, fill=0)
    
    # Logo centrado en la parte superior
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        logo_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
        
        if os.path.exists(logo_path):
            c.drawImage(logo_path, width/2-20*mm, height-50*mm, width=40*mm, height=35*mm, mask='auto', preserveAspectRatio=True)
    except Exception as e:
        print(f"Error al cargar el logo: {str(e)}")
    
    # Título del documento con estilo elegante
    titulo = "CERTIFICADO DE ESTUDIOS"
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, height-60*mm, titulo)
    
    # Ajustar posición inicial
    current_y = height - 80*mm
    
    # Información de la institución
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "JARDIN INFANTIL SONRISAS")
    current_y -= 8*mm
    
    c.setFont("Helvetica-Oblique", 11)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "“Aprendiendo y sonriendo”")
    current_y -= 8*mm
    
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, "Código DANE N° 320001800766")
    current_y -= 8*mm
    
    c.drawCentredString(width/2, current_y, "Aprobado según resolución N° 000959 del 25 de Noviembre de 2024")
    current_y -= 20*mm
    
    # Texto principal del certificado (formato similar al SENA)
    texto_certificado = f"CERTIFICA"
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, texto_certificado)
    current_y -= 15*mm
    
    # Información del estudiante en formato SENA - INCLUIR PROMEDIO
    hoy = datetime.now()
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    
    texto_estudiante = f"Que {matricula.nombres} {matricula.apellidos} identificado/a con "
    texto_estudiante += f"Registro Civil N° {matricula.documento}, "
    texto_estudiante += f"realizó y aprobó satisfactoriamente el año escolar {matricula.año_lectivo} "
    texto_estudiante += f"cursando el grado {matricula.curso.nombre} con un promedio final de {promedio_final} (APROBADO)."
    
    # Dividir texto en líneas
    max_width = width - 2 * margin_left
    lines = []
    words = texto_estudiante.split()
    line = ""
    
    for word in words:
        test_line = f"{line} {word}" if line else word
        if c.stringWidth(test_line, "Helvetica", 11) <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    
    if line:
        lines.append(line)
    
    for line in lines:
        c.setFont("Helvetica", 11)
        c.setFillColor(black)
        c.drawString(margin_left, current_y, line)
        current_y -= 7*mm
    
    current_y -= 10*mm
    
    # Fecha y lugar
    dia_texto = numero_a_texto(hoy.day)
    fecha_formateada = f"Se expide en Valledupar, a los {dia_texto} ({hoy.day:02d}) días del mes de {meses[hoy.month-1]} de {hoy.year}"
    
       # Sección de firma con diseño mejorado
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawCentredString(width/2, current_y, fecha_formateada)
    current_y -= 40*mm  # Más espacio antes de la firma
    
    # Reemplazar esta sección en ambas funciones:
    if rector_firma_url:
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            firma_path = os.path.join(base_dir, 'frontend', 'static', rector_firma_url.lstrip('/static/'))
            if os.path.exists(firma_path):
                # Especificar mask='auto' para manejar transparencia
                c.drawImage(firma_path, width/2-25*mm, current_y-5*mm, width=50*mm, height=20*mm, mask='auto', preserveAspectRatio=True)
                current_y -= 5*mm
            else:
                print(f"Firma no encontrada en: {firma_path}")
        except Exception as e:
            print(f"Error al cargar la firma: {str(e)}")
    
    # Línea de firma DEBAJO de la imagen
    c.setStrokeColor(color_primary)
    c.setLineWidth(0.5)
    c.line(width/2-50*mm, current_y, width/2+50*mm, current_y)
    current_y -= 10*mm  # Espacio después de la línea

    # Información del rector DEBAJO de la línea
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, rector_nombre)
    current_y -= 6*mm

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, f"C.C {rector_identidad}")
    current_y -= 6*mm

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width/2, current_y, "Rector(a)")
    current_y -= 20*mm
    
    # Información de contacto sin recuadro
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "CONTACTO")
    current_y -= 5*mm
    
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(width/2, current_y, "Urbanización Luis Carlos Galán Mz E casa 9")
    current_y -= 5*mm
    c.drawCentredString(width/2, current_y, "jardininfantilsonrisas2023@gmail.com")
    current_y -= 5*mm
    c.drawCentredString(width/2, current_y, "300 149 8933")
  
    c.save()
    buffer.seek(0)
    
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=certificado_{matricula.nombres}_{matricula.apellidos}.pdf'
    return response


@documentos_bp.route('/descargar_todos/<tipo>', methods=['GET'])
@roles_required('admin', 'docente')
def descargar_todos(tipo):
    if tipo not in TIPOS_DOCUMENTOS:
        flash('Tipo de documento no válido.', 'danger')
        return redirect(url_for('documentos.listar_documentos'))
    curso_id = request.args.get('curso', type=int)
    if not curso_id:
        flash('Debe seleccionar un curso para la descarga masiva.', 'danger')
        return redirect(url_for('documentos.listar_documentos'))

    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    if not anio_lectivo:
        flash('No hay un año lectivo activo configurado.', 'danger')
        return redirect(url_for('documentos.listar_documentos'))

    # Verificar permisos del docente
    if not current_user.is_admin():
        asignacion = Asignacion.query.filter_by(
            id_curso=curso_id, id_docente=current_user.id,
            estado='activo', anio_lectivo=anio_lectivo
        ).first()
        if not asignacion:
            flash('No tiene permisos para generar documentos de este curso.', 'danger')
            return redirect(url_for('documentos.listar_documentos'))

    # Obtener todas las matrículas activas del curso
    matriculas = Matricula.query.filter_by(id_curso=curso_id, estado='activo', año_lectivo=anio_lectivo).all()

    if not matriculas:
        flash('No hay estudiantes activos en este curso para generar documentos.', 'warning')
        return redirect(url_for('documentos.listar_documentos', curso=curso_id, tipo=tipo))

    zip_buffer = BytesIO()
    documentos_generados = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for matricula in matriculas:
            pdf_buffer = None
            filename = ""

            if tipo == 'certificados':
                aprobado, promedio = verificar_aprobacion_estudiante(matricula.id)
                if aprobado:
                    pdf_buffer = generar_certificado(matricula, promedio).data
                    filename = f"certificado_{matricula.apellidos}_{matricula.nombres}.pdf"
            elif tipo == 'constancias':
                pdf_buffer = generar_constancia(matricula).data
                filename = f"constancia_{matricula.apellidos}_{matricula.nombres}.pdf"

            if pdf_buffer and filename:
                zf.writestr(filename, pdf_buffer)
                documentos_generados += 1

    if documentos_generados == 0:
        if tipo == 'certificados':
            flash('Ningún estudiante cumplió con el requisito de aprobación para generar certificados.', 'warning')
        else:
            flash('No se generaron documentos.', 'warning')
        return redirect(url_for('documentos.listar_documentos', curso=curso_id, tipo=tipo))

    zip_buffer.seek(0)
    curso_nombre = Curso.query.get(curso_id).nombre.replace(' ', '_')
    zip_filename = f"{tipo.capitalize()}_{curso_nombre}_{anio_lectivo}.zip"

    response = make_response(zip_buffer.read())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename={zip_filename}'
    return response





@documentos_bp.route('/start-task/descargar-todos/<tipo>', methods=['POST'])
@roles_required('admin', 'docente')
def start_descargar_todos(tipo):
    curso_id = request.json.get('curso', type=int)
    if not curso_id:
        return jsonify({'status': 'error', 'message': 'Debe seleccionar un curso.'}), 400

    config = get_active_config()
    anio_lectivo = config['anio'] if config and 'anio' in config else None
    if not anio_lectivo:
        return jsonify({'status': 'error', 'message': 'No hay un año lectivo activo.'}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': 'iniciando', 'progress': 0, 'message': 'Iniciando tarea...'}

    thread = threading.Thread(target=_generar_zip_documentos_en_background, args=(task_id, current_app.app_context(), tipo, curso_id, anio_lectivo, current_user.id))
    thread.start()

    return jsonify({'status': 'ok', 'task_id': task_id})


@documentos_bp.route('/task-status/<task_id>')
@roles_required('admin', 'docente')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'status': 'error', 'message': 'Tarea no encontrada.'}), 404
    return jsonify(task)