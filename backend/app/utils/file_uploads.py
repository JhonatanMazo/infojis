import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
import cv2
import numpy as np
    
def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida"""
    ALLOWED_EXTENSIONS = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'})
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 MB por ejemplo
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH

def get_upload_folder(subfolder='profiles'):
    """Obtiene la ruta completa de la carpeta de uploads según el subfolder"""
    # Mover una carpeta adicional hacia atrás
    upload_base = os.path.normpath(os.path.join(current_app.root_path, '..', '..', 'frontend', 'static', 'uploads'))
    upload_folder = os.path.join(upload_base, subfolder)
    
    # Crear directorios si no existen
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder

def upload_profile_picture(file, documento):
    """Sube una foto de perfil al servidor"""
    if file and allowed_file(file.filename):
        # Generar un nombre único para el archivo
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id = uuid.uuid4().hex[:8]
        safe_documento = secure_filename(documento)[:20]
        new_filename = f"{safe_documento}_{unique_id}.{ext}"
        
        # Obtener la carpeta de destino
        upload_folder = get_upload_folder('profiles')
        filepath = os.path.join(upload_folder, new_filename)
        
        # Guardar el archivo
        file.save(filepath)
        return new_filename
    return None

def remove_profile_picture(filename):
    """Elimina una foto de perfil del servidor"""
    if filename:
        upload_folder = get_upload_folder('profiles')
        filepath = os.path.join(upload_folder, filename)
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                current_app.logger.error(f"Error eliminando foto de perfil: {str(e)}")
                return False
    return False

def upload_documento(file, nombre_base):
    """Sube un documento al servidor"""
    if file and allowed_file(file.filename):
        # Generar un nombre único para el archivo
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id = uuid.uuid4().hex[:8]
        safe_name = secure_filename(nombre_base)[:20]
        new_filename = f"{safe_name}_{unique_id}.{ext}"
         # Obtener la carpeta de destino
        upload_folder = get_upload_folder('documents')  # nueva carpeta para documentos
        filepath = os.path.join(upload_folder, new_filename)
        # Guardar el archivo
        file.save(filepath)
        return new_filename
    return None


def remove_documento(filename):
    """Elimina un documento del servidor"""
    if filename:
        upload_folder = get_upload_folder('documents')
        filepath = os.path.join(upload_folder, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                current_app.logger.error(f"Error eliminando documento: {str(e)}")
    return False


def get_profile_picture_path(filename):
    """Obtiene la ruta relativa del archivo para el frontend"""
    if filename:
        return os.path.join('uploads', 'profiles', filename)
    return None


def upload_rector_firma(file, nombre_base='firma_rector'):
    """Sube la foto de la firma del rector al servidor y remueve el fondo"""
    if file and allowed_file(file.filename)[0]:
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_id = uuid.uuid4().hex[:8]
        safe_name = secure_filename(nombre_base)[:20]
        new_filename = f"{safe_name}_{unique_id}.png"  # Siempre usar PNG para transparencia

        # Carpeta destino para firmas de rector
        upload_folder = get_upload_folder('rector_firma')
        filepath = os.path.join(upload_folder, new_filename)

        try:
            # Leer la imagen
            file_bytes = np.frombuffer(file.read(), np.uint8)
            image = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
            
            # Convertir a RGBA si no lo está
            if image.shape[2] == 3:  # Si es RGB (3 canales)
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
            
            # Crear máscara basada en el color (asumiendo fondo blanco)
            # Umbral para detectar píxeles que no son fondo
            gray = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
            _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
            
            # Aplicar la máscara al canal alpha
            image[:, :, 3] = mask
            
            # Guardar la imagen con transparencia
            cv2.imwrite(filepath, image)
                
            # Retorna la ruta relativa para guardar en la base de datos
            return os.path.join('static', 'uploads', 'rector_firma', new_filename)
        except Exception as e:
            current_app.logger.error(f"Error procesando firma: {str(e)}")
            # Fallback: guardar la imagen original si hay error
            file.seek(0)  # Volver al inicio del archivo
            file.save(filepath)
            return os.path.join('static', 'uploads', 'rector_firma', new_filename)
    return None



def remove_rector_firma(filename):
    """Elimina una foto de la firma del rector del servidor"""
    if filename:
        upload_folder = get_upload_folder('rector_firma')
        filepath = os.path.join(upload_folder, filename)
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                current_app.logger.error(f"Error eliminando foto de la firma: {str(e)}")
                return False
    return False