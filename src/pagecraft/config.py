from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure OpenAI — env vars: AZURE_OPENAI_*
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # App — env vars: PAGECRAFT_*
    db_path: str = Field(
        default="./data/pagecraft.db",
        validation_alias=AliasChoices("PAGECRAFT_DB_PATH", "db_path"),
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("PAGECRAFT_HOST", "host"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PAGECRAFT_PORT", "port"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("PAGECRAFT_DEBUG", "debug"),
    )
    base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PAGECRAFT_BASE_URL", "base_url"),
    )

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    @property
    def prompts_dir(self) -> Path:
        return self.project_root / "prompts"

    @property
    def components_yaml_path(self) -> Path:
        return Path(__file__).parent / "components.yaml"
