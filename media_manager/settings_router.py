from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from urllib.parse import urlsplit
from media_manager.auth.users import current_superuser
from media_manager.configuration import fields_for_browser, stage_settings, settings_file, config_file

router = APIRouter(dependencies=[Depends(current_superuser)])
class SettingsUpdate(BaseModel):
    values: dict

@router.get('')
def read_settings():
    return {'fields': fields_for_browser(), 'restart_required': settings_file(True).exists(),'connections_setup_pending':(config_file().parent/'connections-setup.json').exists()}

@router.put('')
def save_settings(body: SettingsUpdate, request: Request):
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403,'Fremde Herkunft nicht erlaubt')
    try: result = stage_settings(body.values, apply_live=True)
    except ValueError as error: raise HTTPException(400,str(error)) from None
    except OSError: raise HTTPException(503,'Einstellungen konnten nicht gespeichert werden. Schreibrechte des Konfigurationsordners prüfen.') from None
    return {**result,'message':'Änderungen gespeichert. Für bestimmte Einstellungen ist ein Neustart der Anwendung erforderlich.' if result['restart_required'] else 'Änderungen gespeichert und übernommen.'}

@router.post('/finish-setup')
def finish_setup(request:Request):
    origin=request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):raise HTTPException(403,'Fremde Herkunft nicht erlaubt')
    (config_file().parent/'connections-setup.json').unlink(missing_ok=True)
    return {'saved':True}

from pydantic import EmailStr
class MailTest(BaseModel):
    recipient:EmailStr|None=None
@router.post('/mail-test')
def mail_test(body:MailTest):
    from media_manager.auth.mail import mail_ready
    from media_manager.notification.utils import send_email
    if not mail_ready():raise HTTPException(400,'Configure the SMTP server and sender email first.')
    from media_manager.config import MediaManagerConfig
    import smtplib,ssl
    c=MediaManagerConfig().notifications.smtp_config
    try:
        if body.recipient:
            send_email('MediaManager – SMTP test','<p>MediaManager SMTP connection and email delivery are working.</p>',str(body.recipient))
        else:
            transport=smtplib.SMTP_SSL if c.use_ssl else smtplib.SMTP
            options={'timeout':15}
            if c.use_ssl:options['context']=ssl.create_default_context()
            with transport(c.smtp_host,c.smtp_port,**options) as server:
                server.ehlo()
                if c.use_tls and not c.use_ssl:server.starttls(context=ssl.create_default_context());server.ehlo()
                if c.smtp_user:server.login(c.smtp_user,c.smtp_password)
    except Exception:raise HTTPException(502,'SMTP connection or delivery failed. Check server, port, TLS and credentials.') from None
    return {'sent':bool(body.recipient),'connected':True}
