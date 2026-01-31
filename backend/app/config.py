"""
Application Configuration

Centralized configuration management using environment variables and Pydantic settings.
"""

import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    app_name: str = "Code Analysis Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    llm_model: str = "gpt-4"
    embed_model: str = "text-embedding-ada-002"
    
    # Storage Configuration
    storage_dir: str = "./graph_storage"
    eip_cache_dir: str = "./.eip_cache"
    specs_dir: str = "./specs"
    
    # Git Configuration
    github_token: Optional[str] = None
    gitlab_token: Optional[str] = None
    github_webhook_secret: Optional[str] = None
    gitlab_webhook_token: Optional[str] = None
    
    # CORS Configuration
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function to get settings
settings = get_settings()


# Path helpers
def get_storage_path() -> Path:
    """Get the storage directory path."""
    path = Path(settings.storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_eip_cache_path() -> Path:
    """Get the EIP cache directory path."""
    path = Path(settings.eip_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_specs_path() -> Path:
    """Get the specifications directory path."""
    path = Path(settings.specs_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
