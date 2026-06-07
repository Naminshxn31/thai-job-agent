"""
app/config.py
Central config — reads from environment variables / .env file
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "thai_jobs"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    cors_origins: list[str] = ["http://localhost:8501"]

    # Agent
    agent_max_turns: int = 10
    agent_temperature: float = 0.2

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    # On Streamlit Cloud, read from st.secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return Settings(
                gemini_api_key=st.secrets["GEMINI_API_KEY"],
                gemini_model=st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash"),
                gemini_embedding_model=st.secrets.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
            )
    except Exception:
        pass
    return Settings()
