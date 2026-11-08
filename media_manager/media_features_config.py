from pydantic import field_validator
from pydantic_settings import BaseSettings
class EmbyConfig(BaseSettings):
    enabled:bool=False
    url:str=''
    api_key:str=''
    @field_validator('url')
    @classmethod
    def valid_url(cls,value):
        from urllib.parse import urlsplit
        if value:
            u=urlsplit(value)
            if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('Use an HTTP(S) server address without credentials.')
        return value.rstrip('/')
