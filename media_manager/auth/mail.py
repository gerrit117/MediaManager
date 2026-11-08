"""Account mail uses the same private SMTP settings as notifications."""
from html import escape
from urllib.parse import urljoin,urlencode
from fastapi_users.jwt import generate_jwt
from media_manager.config import MediaManagerConfig
from media_manager.notification.utils import send_email
import logging
log=logging.getLogger(__name__)
def mail_ready():
    c=MediaManagerConfig().notifications.smtp_config
    return bool(c.smtp_host and c.from_email)
def send_link(email,token,kind,language="de"):
    c=MediaManagerConfig();path='web/login/verify' if kind=='verify' else 'web/login/reset-password'
    link=urljoin(str(c.misc.frontend_url).rstrip('/')+'/',path)+'#'+urlencode({'token':token})
    title=('E-Mail bestätigen' if kind=='verify' else 'Passwort zurücksetzen') if language=='de' else ('Verify email' if kind=='verify' else 'Reset password')
    from media_manager.notification.template import render
    html=render(title,escape('Öffne den folgenden Link. Falls du dies nicht angefordert hast, ignoriere diese E-Mail.' if language=='de' else 'Open the following link. If you did not request this, ignore this email.'),link,language)
    try:send_email('MediaManager – '+title,html,email);return True
    except Exception as error:log.warning('Account email delivery failed (%s).',type(error).__name__);return False
def send_verification(user):
    from media_manager.auth.users import SECRET
    token=generate_jwt({'sub':str(user.id),'email':user.email,'aud':'fastapi-users:verify'},SECRET,86400)
    return send_link(user.email,token,'verify',getattr(user,'preferred_language',None) or 'de')
def notify_admins(subject,message):
    c=MediaManagerConfig()
    if not c.auth.administrator_mail_enabled or not mail_ready():return
    for email in c.auth.admin_emails:
        try:send_email('MediaManager – '+subject,'<p>'+escape(message)+'</p>',email)
        except Exception as error:log.warning('Administrator email delivery failed (%s).',type(error).__name__)
