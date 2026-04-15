
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    
    ollama_base_url: str = Field("http://localhost:11434", alias="OLLAMA_BASE_URL")
    text_model: str = Field("llama3", alias="TEXT_MODEL")
    vision_model: str = Field("llava", alias="VISION_MODEL")
    max_iterations: int = Field(15, alias="MAX_ITERATIONS")
    max_actions_per_plan: int = Field(10, alias="MAX_ACTIONS_PER_PLAN")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


cfg = Settings()
