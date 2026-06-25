from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "huihui-qwen3.6-35b-a3b-abliterated-mtp"
    llm_api_key: str = "lm-studio"
    llm_temperature: float = 0.85
    llm_top_p: float = 0.92
    llm_max_tokens: int = 2048

    secret_key: str = "tavern-mixer-dev-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    host: str = "127.0.0.1"
    port: int = 8787
    database_url: str = f"sqlite:///{DATA_DIR / 'tavern.db'}"
    upload_dir: Path = UPLOAD_DIR
    max_upload_mb: int = 5

    cors_origins: list[str] = ["http://127.0.0.1:8787", "http://localhost:8787"]

    allow_registration: bool = False
    account_manager_username: str = "admin"

    seed_admin_username: str = "admin"
    seed_admin_password: str = "changeme"


settings = Settings()
