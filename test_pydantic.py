import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class LogConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTSALINHA_LOG__",
        env_nested_delimiter="__",
        extra="ignore",
    )
    dir: str = "default_dir"
    max_bytes: int = 100

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )
    log: LogConfig = Field(default_factory=LogConfig)

os.environ["BOTSALINHA_LOG__DIR"] = "env_dir"
os.environ["BOTSALINHA_LOG__MAX_BYTES"] = "200"

s = Settings()
print(s.log.dir, s.log.max_bytes)
