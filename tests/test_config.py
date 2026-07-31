from src.core.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.zai_api_key == ""
    assert settings.log_level == "INFO"


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("ZAI_API_KEY", "sk-zai-test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.zai_api_key == "sk-zai-test"
    assert settings.log_level == "DEBUG"
