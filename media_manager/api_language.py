"""Translate application-owned HTTP errors; never translate media/user data."""
from starlette.responses import JSONResponse

ERRORS={
 'Monatliches Anfragekontingent ausgeschöpft. Es wird am ersten Tag des nächsten Monats (Europe/Berlin) erneuert.':'Monthly request quota exhausted. It resets on the first day of next month (Europe/Berlin).',
 'Konto ist deaktiviert':'Account is disabled.',
 'Benutzer nicht gefunden':'User not found.',
 'Fremde Herkunft nicht erlaubt':'Cross-origin request is not allowed.',
 'Einrichtungscode ist falsch':'Incorrect setup code.',
 'Bereits eingerichtet':'Already configured.',
 'Datenbankverbindung ist unvollständig':'Database connection settings are incomplete.',
 'PostgreSQL nicht erreichbar oder Zugangsdaten ungültig':'PostgreSQL is unreachable or credentials are invalid.',
 'Containerpfade müssen absolut sein':'Container paths must be absolute.',
 'Bibliotheks- oder Downloadpfad nicht schreibbar; UID/GID und Mounts prüfen':'Library or download path is not writable; check UID/GID and mounts.',
 'Admin-E-Mail oder Passwort ungültig':'Invalid administrator email or password.',
 'Automatisch erzeugte Datenbankzugangsdaten fehlen':'Generated database credentials are missing.',
}
async def http_error(request,error):
    language=request.cookies.get('mm_language') or request.headers.get('accept-language','en').split(',')[0]
    detail=error.detail
    if isinstance(detail,str):
        if not language.startswith('de'):detail=ERRORS.get(detail,detail)
        elif detail=='Forbidden':detail='Keine Berechtigung'
    return JSONResponse({'detail':detail},status_code=error.status_code,headers=error.headers)
