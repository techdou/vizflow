import os
from typing import Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Demo mode
    DEMO_MODE: bool = True
    
    # Database
    DB_URL: str = "sqlite:///./data/db.sqlite3"
    
    # Storage paths
    DATASETS_DIR: str = "./data/datasets"
    THUMBNAILS_DIR: str = "./data/thumbnails"
    
    # File limits
    MAX_UPLOAD_SIZE: int = 25 * 1024 * 1024  # 25MB
    MAX_ROWS: int = 200000
    MAX_COLUMNS: int = 100
    
    # Timeouts (seconds)
    CHART_GENERATION_TIMEOUT: int = 60
    THUMBNAIL_TIMEOUT: int = 4
    ANALYSIS_TIMEOUT: int = 30
    
    # LLM settings (DeepSeek V4 series)
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    
    # Vision/Multimodal settings
    GLM_API_KEY: Optional[str] = None
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4v"

    # Analysis provider: "text" (DeepSeek, default) or "vision" (GLM multimodal)
    ANALYSIS_PROVIDER: str = "text"

    # Auth (fix #3): if VIZFLOW_API_KEY is set, all mutating/LLM endpoints
    # require header `X-API-Key: <key>`. If empty/unset, auth is disabled
    # (local dev only — never deploy publicly with it unset).
    VIZFLOW_API_KEY: Optional[str] = None

    # Concurrency limit (fix #3): global in-flight LLM calls (chart gen + analysis).
    # Enforced via an asyncio.Semaphore in main.py.
    MAX_CONCURRENT_LLM: int = 3

    # Rate limiting
    MAX_CONCURRENT_PER_USER: int = 2

    # CORS
    CORS_ORIGINS: Union[list[str], str] = "http://localhost:3000,http://127.0.0.1:3000"
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra='ignore'  # Ignore unknown fields from environment
    )

settings = Settings()

# Ensure directories exist
os.makedirs(settings.DATASETS_DIR, exist_ok=True)
os.makedirs(settings.THUMBNAILS_DIR, exist_ok=True)
