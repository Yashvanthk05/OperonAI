from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    text_model: str = Field("gemma4:e4b", env="TEXT_MODEL")
    vision_model: str = Field("llava", env="VISION_MODEL")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    max_iterations: int = Field(10, env="MAX_ITERATIONS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


cfg = Settings()
