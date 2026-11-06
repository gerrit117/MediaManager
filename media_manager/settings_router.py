from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from urllib.parse import urlsplit
from media_manager.auth.users import current_superuser
from media_manager.configuration import fields_for_browser, stage_settings, settings_file

router = APIRouter(dependencies=[Depends(current_superuser)])
class SettingsUpdate(BaseModel):
    values: dict

@router.get('')
def read_settings():
    return {'fields': fields_for_browser(), 'restart_required': settings_file(True).exists()}

@router.put('')
def save_settings(body: SettingsUpdate, request: Request):
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403,'Fremde Herkunft nicht erlaubt')
    try: stage_settings(body.values)
    except ValueError as error: raise HTTPException(400,str(error)) from None
    except OSError: raise HTTPException(503,'Einstellungen konnten nicht gespeichert werden. Schreibrechte des Konfigurationsordners prüfen.') from None
    return {'restart_required':True,'message':'Gespeichert. Wird beim nächsten Containerstart wirksam.'}
