from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
class Settings(BaseSettings):
    APP_ENV: Literal["dev","prod","test"] = "dev"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    CHROMA_DIR: str = "./data/vectors/chroma"
    LLM_BACKEND: Literal["none","local"] = "none"
    LLM_MODEL: str = "llama3.1:8b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 200
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
