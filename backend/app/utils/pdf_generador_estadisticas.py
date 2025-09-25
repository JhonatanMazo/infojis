from fpdf import FPDF
from datetime import datetime
import base64
import os

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Estadísticas Académicas', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 10, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generate_statistics_pdf(graficas, grado):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Título del reporte
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f'Estadísticas Académicas - {grado if grado != "todos" else "Todos los grados"}', 0, 1, 'C')
    pdf.ln(10)
    
    # Agregar cada gráfica al PDF
    for grafica in graficas:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, grafica['nombre'], 0, 1, 'L')
        pdf.ln(5)
        
        # Guardar imagen temporalmente
        img_data = grafica['imagen'].split(',')[1]
        temp_img_path = f"temp_{grafica['nombre']}.png"
        with open(temp_img_path, 'wb') as f:
            f.write(base64.b64decode(img_data))
        
        # Insertar imagen en PDF
        pdf.image(temp_img_path, x=10, w=190)
        pdf.ln(10)
        
        # Eliminar archivo temporal
        os.remove(temp_img_path)
    
    return pdf.output(dest='S').encode('latin1')