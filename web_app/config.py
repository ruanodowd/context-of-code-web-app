from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache
from typing import get_type_hints

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./metrics.db"
    
    # Application
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    DEBUG: bool = False
    
    # Security
    API_KEY: str
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"
    
    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> List[str]:
        return self.CORS_ORIGINS.split(",") if isinstance(self.CORS_ORIGINS, str) else self.CORS_ORIGINS
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
