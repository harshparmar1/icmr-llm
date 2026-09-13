import os
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application Information
    PROJECT_NAME: str = "ICMR-Guided Clinical Workflow Intelligence System"
    PROJECT_SHORT_NAME: str = "ICMR-STW AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Storage paths
    BASE_DIR: Path = BASE_DIR
    BASE_PATH: Path = BASE_DIR
    DATA_RAW_DIR: Path = BASE_DIR / "data" / "raw"
    DATA_PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    DATA_METADATA_DIR: Path = BASE_DIR / "data" / "metadata"

    # Database settings (PostgreSQL target, SQLite dev fallback)
    DATABASE_URL: str = "sqlite:///./icmr_stw.db"

    # Vector DB (ChromaDB)
    CHROMA_USE_CLOUD: bool = False
    CHROMA_API_KEY: str = ""
    CHROMA_TENANT: str = "default_tenant"
    CHROMA_DATABASE: str = "default_database"
    CHROMA_PERSIST_DIRECTORY: str = str(BASE_DIR / "vector_db")
    CHROMA_COLLECTION_NAME: str = "icmr_stw_chunks"

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # LLM / SLM Provider Settings
    LLM_PROVIDER: str = "mistral"  # "mistral", "mock", "local", "openai", "groq"
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "ministral-8b-latest"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    LOCAL_SLM_BASE_URL: str = "http://localhost:11434/v1"
    LOCAL_SLM_MODEL: str = "qwen2.5:7b"

    # Retrieval & RAG
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_RELEVANCE_THRESHOLD: float = 0.45
    ENABLE_HYBRID_RETRIEVAL: bool = True
    BM25_WEIGHT: float = 0.4
    DENSE_WEIGHT: float = 0.6

    # Safety & Grounding
    GROUNDING_STRICT_MODE: bool = True
    MAX_QUERY_LENGTH: int = 500
    MIN_EVIDENCE_TOKENS: int = 30
    REQUIRE_ICMR_CITATION: bool = True

    # System disclaimers
    CLINICAL_SAFETY_DISCLAIMER: str = (
        "This platform is an evidence-grounded clinical decision-support and educational tool "
        "derived exclusively from Indian Council of Medical Research (ICMR) Standard Treatment "
        "Workflows (STWs). It is NOT an autonomous medical doctor and does not replace qualified "
        "medical judgement or individualized clinical assessment."
    )


settings = Settings()
