from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, HexColor
import os


def generar_comprobante_pago_pdf(id_pago, pago_data):
    """
    Genera un comprobante de pago premium con diseño elegante
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Configurar márgenes
    margin_left = 15 * mm
    margin_right = width - (15 * mm)
    margin_top = height - (15 * mm)
    current_y = margin_top
    
    # Colores premium
    color_primary = HexColor("#2C3E50")  # Azul oscuro elegante
    color_accent = HexColor("#E67E22")   # Naranja dorado
    color_light = HexColor("#ECF0F1")    # Gris claro
    color_success = HexColor("#27AE60")  # Verde éxito
    color_pending = HexColor("#E74C3C")  # Rojo para pendiente
    
    # Fondo con textura sutil
    c.setFillColor(HexColor("#FBFCFC"))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Marco decorativo
    c.setStrokeColor(color_primary)
    c.setLineWidth(0.5)
    c.roundRect(10*mm, 10*mm, width-20*mm, height-20*mm, 5*mm, stroke=1, fill=0)
    
    # Encabezado con logo ajustado
    try:
        # Obtener la ruta correcta del logo (en frontend/static/img/)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        logo_path = os.path.join(base_dir, 'frontend', 'static', 'img', 'logotipo.png')
        
        if os.path.exists(logo_path):
            # Logo ajustado para que no sobresalga
            c.drawImage(logo_path, margin_left, height-47*mm, width=35*mm, height=40*mm, mask='auto', preserveAspectRatio=True)
        else:
            # Texto alternativo si el logo no existe
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(color_primary)
            c.drawString(margin_left, height-30*mm, "JARDÍN INFANTIL")
            c.drawString(margin_left, height-35*mm, "SONRISAS")
    except Exception as e:
        print(f"Error al cargar el logo: {str(e)}")
    
    # Título principal
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, height-30*mm, "COMPROBANTE DE PAGO")
    
    # Se quitó el subtítulo "Transacción Exitosa"
    current_y = height - 45*mm  # Bajamos esta línea para más espacio
    
    # Línea decorativa - bajada para dar más espacio al logo
    c.setStrokeColor(color_accent)
    c.setLineWidth(1)
    c.line(margin_left, current_y, margin_right, current_y)
    current_y -= 12*mm  # Aumentamos el espacio después de la línea
    
    # Sección de información de pago
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "DETALLES DE LA TRANSACCIÓN")
    current_y -= 8*mm
    
     # Información alineada en dos columnas
    label_width = 40 * mm
    value_x = margin_left + label_width + 5*mm
    
    # Referencia
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Referencia:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(value_x, current_y, f"PAY-{id_pago:06d}")
    current_y -= 8*mm
    
    # Fecha
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Fecha:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    fecha_str = pago_data['fecha_pago'].strftime('%d/%m/%Y') if hasattr(pago_data['fecha_pago'], 'strftime') else str(pago_data['fecha_pago'])
    c.drawString(value_x, current_y, fecha_str)
    current_y -= 8*mm
    
    # Concepto
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Concepto:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(value_x, current_y, pago_data['concepto'].upper())
    current_y -= 8*mm
    
    # Método de pago
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Método de pago:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(value_x, current_y, pago_data['metodo_pago'].capitalize())
    current_y -= 8*mm
    
    # Estado con color condicional
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Estado:")
    c.setFont("Helvetica-Bold", 11)
    
    # Cambiar color según el estado
    estado = pago_data['estado'].lower()
    if estado == 'pagado':
        c.setFillColor(color_success)
    elif estado == 'pendiente':
        c.setFillColor(color_pending)
    else:
        c.setFillColor(black)
        
    c.drawString(value_x, current_y, pago_data['estado'].upper())
    current_y -= 15*mm
    
    # Monto destacado - Cambiar según el estado
    current_y -= 20*mm
    
    # Determinar texto y color según el estado
    if pago_data['estado'].lower() == 'pagado':
        texto_monto = "TOTAL PAGADO"
        color_monto = color_success
    else:
        texto_monto = "TOTAL PENDIENTE"
        color_monto = color_pending
    
    c.setFillColor(color_monto)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, current_y, texto_monto)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, current_y-10*mm, f"$ {pago_data['monto']:,.0f} COP")
    current_y -= 25*mm
    
    # Línea decorativa
    c.setStrokeColor(color_accent)
    c.setLineWidth(1)
    c.line(margin_left, current_y, margin_right, current_y)
    current_y -= 10*mm
    
    # Información del estudiante
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "INFORMACIÓN DEL ESTUDIANTE")
    current_y -= 8*mm
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Nombre completo:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(margin_left + 50*mm, current_y, f"{pago_data['estudiante_nombre']} {pago_data['estudiante_apellido']}")
    current_y -= 6*mm
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Documento:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(margin_left + 50*mm, current_y, pago_data.get('estudiante_documento', 'N/A'))
    current_y -= 6*mm
    
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(color_primary)
    c.drawString(margin_left, current_y, "Curso:")
    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    c.drawString(margin_left + 50*mm, current_y, pago_data['curso_nombre'])
    current_y -= 15*mm
    
    # Línea decorativa
    c.setStrokeColor(color_accent)
    c.setLineWidth(1)
    c.line(margin_left, current_y, margin_right, current_y)
    current_y -= 10*mm
    
    # Información de la institución
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "JARDÍN INFANTIL SONRISAS")
    current_y -= 6*mm
    
    c.setFont("Helvetica", 10)
    c.setFillColor(color_primary)
    c.drawCentredString(width/2, current_y, "APRENDIENDO Y SONRIENDO")
    current_y -= 5*mm
    
    c.setFont("Helvetica", 9)
    c.setFillColor(black)
    c.drawCentredString(width/2, current_y, "Codigo Dane: 320001800766 • Teléfono: 300 149 8933")
    current_y -= 4*mm
    c.drawCentredString(width/2, current_y, "Dirección: Urbanizacion Luis Carlos Galán Mz E Casa 9 • Valledupar, Colombia")
    current_y -= 10*mm
    
    # Pie de página
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor("#777777"))
    c.drawCentredString(width/2, 20*mm, "Este comprobante es generado automáticamente y no requiere firma.")
    c.drawCentredString(width/2, 15*mm, "VIGILADO SUPERINTENDENCIA FINANCIERA DE COLOMBIA")
    
    
    c.save()
    buffer.seek(0)
    return buffer