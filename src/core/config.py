from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    zai_api_key: str = ""
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}


settings = Settings()
