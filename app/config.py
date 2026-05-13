"""Application configuration using Pydantic settings"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Ray_jr Knowledge Base"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql://ray_jr_user:changeme@localhost:5432/ray_jr",
        description="PostgreSQL connection string"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )

    # Qdrant Vector Store
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant HTTP port")
    qdrant_grpc_port: int = Field(default=6334, description="Qdrant gRPC port")

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT signing secret"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration in minutes"
    )

    # API Keys
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")
    openai_api_key: str = Field(default="", description="OpenAI API key")

    # LLM Provider Configuration
    llm_provider: str = Field(default="deepseek", description="LLM provider: deepseek / openai / anthropic")
    llm_api_key: str = Field(default="", description="Unified LLM API key")
    llm_base_url: str = Field(default="https://api.deepseek.com", description="LLM API base URL")
    llm_model: str = Field(default="deepseek-chat", description="LLM model name")

    # RAG Engine
    rag_model: str = Field(default="deepseek-chat", description="LLM model for RAG")
    rag_max_context_tokens: int = Field(default=100000, description="Max context window")
    rag_top_k: int = Field(default=5, description="Number of documents to retrieve")

    # Knowledge Base Repository
    knowledge_base_repo: str = Field(
        default="https://github.com/rayallen1990/-ray_jr-knowledge-base.git",
        description="Git repository URL for knowledge base data"
    )
    knowledge_base_path: str = Field(
        default="./data",
        description="Local path to clone/sync knowledge base"
    )
    knowledge_base_branch: str = Field(
        default="main",
        description="Branch to use from knowledge base repo"
    )
    knowledge_base_auto_sync: bool = Field(
        default=True,
        description="Auto sync knowledge base on startup"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
