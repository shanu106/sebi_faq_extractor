"""
SEBI FAQ System - Core Configuration
"""

import os
from dotenv import load_dotenv

# Explicitly load environment variables from .env
load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "SEBI FAQ Intelligent System"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql+psycopg2://sebi_user:sebi_password@localhost:5432/sebi_faq_db"
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "faq_embeddings"
    
    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast, efficient model
    embedding_dimension: int = 384
    
    # API
    api_prefix: str = "/api/v1"
    cors_origins: list = ["*"]
    
    # Auth
    jwt_secret: str = "supersecretkeyforadminauthsebi"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
print(f"==================================================")
print(f"  Loaded Database URL: {settings.database_url}")
print(f"==================================================")
