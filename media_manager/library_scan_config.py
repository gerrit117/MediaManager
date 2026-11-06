from pydantic import Field, model_validator
from pydantic_settings import BaseSettings,SettingsConfigDict
from urllib.parse import urlsplit
from pathlib import PurePosixPath

class LibraryScanConfig(BaseSettings):
    model_config=SettingsConfigDict(hide_input_in_errors=True)
    automatic: bool=False
    interval_hours: int=Field(24,ge=1,le=168)
    radarr_url: str=''
    radarr_api_key: str=''
    radarr_root: str='/media'
    sonarr_url: str=''
    sonarr_api_key: str=''
    sonarr_root: str='/media'
    @model_validator(mode='after')
    def validate_sources(self):
        for name in ['radarr','sonarr']:
            url=getattr(self,name+'_url')
            if url:
                parsed=urlsplit(url)
                if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Invalid library metadata source URL')
            if not PurePosixPath(getattr(self,name+'_root')).is_absolute():raise ValueError('Source root must be absolute')
        return self

