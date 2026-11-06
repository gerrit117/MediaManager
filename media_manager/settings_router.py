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
