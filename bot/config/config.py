from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str


    REF_LINK: str = "https://t.me/MemesLabBot/MemesLab?startapp=2YFTB2"

    AUTO_TASK: bool = True
    AUTO_UPGRADE: bool = True
    AUTO_CIPHER: bool = True

    DELAY_EACH_ACCOUNT: list[int] = [20, 30]
    DELAY_EACH_ROUND:list[int] = [3600, 4200]

    ADVANCED_ANTI_DETECTION: bool = False

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()

