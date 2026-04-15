"""Application settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration loaded from .env file and environment variables."""

    ollama_base_url: str = Field("http://localhost:11434", alias="OLLAMA_BASE_URL")
    text_model: str = Field("llama3", alias="TEXT_MODEL")
    vision_model: str = Field("llava", alias="VISION_MODEL")
    max_iterations: int = Field(15, alias="MAX_ITERATIONS")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


cfg = Settings()
