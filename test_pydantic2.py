import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogConfig(BaseSettings):
    dir: str = "default_dir"
    max_bytes: int = 100


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )
    log: LogConfig = Field(
        default_factory=LogConfig, validation_alias=AliasChoices("BOTSALINHA_LOG", "LOG")
    )


os.environ["BOTSALINHA_LOG__DIR"] = "env_dir"
os.environ["BOTSALINHA_LOG__MAX_BYTES"] = "200"

s = Settings()
print(f"Dir: {s.log.dir}, Max Bytes: {s.log.max_bytes}")
