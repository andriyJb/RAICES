"""Envío de correos (solo se usa para recuperar la contraseña).

Con SMTP configurado se envía el mensaje. Sin SMTP:
- en desarrollo, el enlace se escribe en el registro del servidor para poder probar el flujo;
- en producción NO se envía nada y se avisa en el registro (la función devuelve False).
"""
import logging
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def smtp_configurado(config):
    return bool(config.get("SMTP_HOST") and config.get("SMTP_REMITENTE"))


def enviar_recuperacion(config, destinatario, enlace):
    """Devuelve True si el correo salió (o, en desarrollo, si el enlace quedó en el registro)."""
    if not smtp_configurado(config):
        if config["ENTORNO"] == "production":
            log.error("Recuperación de contraseña solicitada, pero SMTP_HOST/SMTP_REMITENTE no están configurados.")
            return False
        log.warning("[DESARROLLO] Enlace de recuperación para %s: %s", destinatario, enlace)
        return True

    mensaje = EmailMessage()
    mensaje["Subject"] = "Raíces · Restablecer tu contraseña"
    mensaje["From"] = config["SMTP_REMITENTE"]
    mensaje["To"] = destinatario
    mensaje.set_content(
        "Recibimos una solicitud para restablecer tu contraseña en Raíces.\n\n"
        f"Abre este enlace (vale {config['MINUTOS_TOKEN_RECUPERACION']} minutos y solo se puede usar una vez):\n"
        f"{enlace}\n\nSi no fuiste tú, ignora este mensaje: tu contraseña no cambiará.\n")
    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=15) as servidor:
            servidor.starttls()
            if config["SMTP_USUARIO"]:
                servidor.login(config["SMTP_USUARIO"], config["SMTP_CLAVE"])
            servidor.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as e:
        log.error("No se pudo enviar el correo de recuperación (%s)", type(e).__name__)
        return False
    return True
