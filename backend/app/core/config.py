from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env.local',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    database_url: str
    environment: str = 'development'
    frontend_url: str = 'http://localhost:5173'

    anthropic_api_key: str
    cohere_api_key: str = ''
    gmail_client_id: str = ''
    gmail_client_secret: str = ''
    gmail_redirect_uri: str = ''
    gmail_scopes: str = (
        'https://www.googleapis.com/auth/gmail.readonly,'
        'https://www.googleapis.com/auth/gmail.compose'
    )
    poll_interval_minutes: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
