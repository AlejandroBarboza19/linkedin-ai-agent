from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    linkedin_access_token: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}


settings = Settings()
