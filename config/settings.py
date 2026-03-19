from pydantic_settings import BaseSettings


class AlpacaSettings(BaseSettings):
    api_key: str
    secret_key: str
    paper: bool = True

    class Config:
        env_prefix = "ALPACA_"
        env_file = ".env"


class AppSettings(BaseSettings):
    alpaca: AlpacaSettings = AlpacaSettings()
    log_level: str = "INFO"
    data_dir: str = "./data"
    log_dir: str = "./logs"
