import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from media_manager.config import MediaManagerConfig

log = logging.getLogger(__name__)


def send_email(subject: str, html: str, addressee: str) -> None:
    email_conf = MediaManagerConfig().notifications.smtp_config
    message = MIMEMultipart()
    message["From"] = email_conf.from_email
    message["To"] = addressee
    message["Subject"] = str(subject)
    message.attach(MIMEText(html, "html"))

    transport=smtplib.SMTP_SSL if email_conf.use_ssl else smtplib.SMTP
    options={'timeout':15}
    if email_conf.use_ssl:options['context']=ssl.create_default_context()
    with transport(email_conf.smtp_host, email_conf.smtp_port, **options) as server:
        if email_conf.use_tls and not email_conf.use_ssl:
            server.starttls(context=ssl.create_default_context())
        if email_conf.smtp_user:
            server.login(email_conf.smtp_user, email_conf.smtp_password)
        server.sendmail(email_conf.from_email, addressee, message.as_string())

    log.info(f"Successfully sent email to {addressee} with subject: {subject}")
