from pydantic_settings import BaseSettings
from typing import Optional, Literal
import os


class Settings(BaseSettings):
    """Application settings and configuration"""
    
    model_config = {
        "extra": "ignore",  # Ignore extra environment variables
        "env_file": ".env",
        "case_sensitive": True
    }
    
    # Application
    APP_NAME: str = "ChemBot API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "chembot"
    
    # Security & JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24 * 7  # 7 days
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list = [".pdf", ".txt", ".docx", ".md"]
    
    # LLM Configuration (LiteLLM)
    LLM_MODEL: str = "gpt-4o-mini"  # Can be: gpt-4, claude-3, gemini-pro, etc.
    LLM_API_KEY: Optional[str] = None  # Will use OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = "text-embedding-3-small"  # OpenAI embedding model
    EMBEDDING_DIMENSION: int = 1536
    
    # Vector Database Configuration
    VECTOR_DB_PROVIDER: Literal["pinecone", "weaviate"] = "pinecone"
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    PINECONE_INDEX_NAME: str = "chembot"
    WEAVIATE_URL: Optional[str] = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    
    # Chunking Configuration
    CHUNK_SIZE: int = 800  # Target chunk size in words
    CHUNK_OVERLAP: int = 150  # Overlap between chunks
    CHUNKING_STRATEGY: Literal["heuristic", "semantic", "intelligent"] = "semantic"
    
    # Chatbot Configuration
    ENABLE_STREAMING: bool = True
    PROMPTS_FILE: str = "src/backend/prompts.yaml"
    CONVERSATION_HISTORY_LENGTH: int = 5  # Number of previous exchanges to keep in context
    ENABLE_QUERY_CLASSIFICATION: bool = True
    
    # Redis Caching
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_ENABLED: bool = True
    REDIS_CACHE_TTL: int = 60 * 60 * 24 * 7  # 7 days in seconds
    
    # Rate Limiting
    LLM_MAX_CONCURRENT_REQUESTS: int = 5  # Maximum parallel LLM requests
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: float = 1.0  # seconds
    LLM_RETRY_BACKOFF: float = 2.0  # exponential backoff multiplier
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


# Create settings instance
settings = Settings()

# Create upload directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

