from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://sapia:sapia_dev@localhost:5432/sapia"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = ""
    upload_dir: str = "/data/uploads"
    openai_api_key: str = ""
    embedding_dimensions: int = 384
    max_upload_mb: int = 20
    max_pdf_pages: int = 20
    rag_top_k: int = 5
    openai_chat_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 120
    batch_llm_workers: int = 4

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        url = value.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def strip_openai_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url.rstrip("/"))
        return origins


settings = Settings()
