import smtplib
from flask import current_app

def send_email(msg):
    """
    Función centralizada para enviar correos electrónicos usando smtplib.
    Utiliza la configuración de la aplicación Flask.

    Args:
        msg (email.message.Message): El objeto del mensaje a enviar.

    Returns:
        bool: True si el correo se envió con éxito, False en caso contrario.
        str: Un mensaje de éxito o el error ocurrido.
    """
    try:
        with smtplib.SMTP(
            current_app.config['MAIL_SERVER'],
            current_app.config['MAIL_PORT'],
            timeout=current_app.config.get('MAIL_TIMEOUT', 30)
        ) as server:
            server.starttls()
            server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True, "Correo enviado exitosamente."
    except Exception as e:
        current_app.logger.error(f"Error al enviar correo: {str(e)}", exc_info=True)
        return False, str(e)