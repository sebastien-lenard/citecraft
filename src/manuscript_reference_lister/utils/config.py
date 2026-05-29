from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import (
    EmailStr,
    Field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from manuscript_reference_lister.schemas import (
    HttpsUrlStr,
    UrlWithObjectName,
)


class AppConfig(BaseSettings):
    """Configuration loader and validator for the environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        json_inner_max_depth=2,  # Force to parse complex strings from .env
    )

    # --- Directory Paths ---
    local_repo_dir_path: Path = Field(default=Path("repo"), alias="LOCAL_REPO_DIR_PATH")
    output_dir_path: Path = Field(default=Path("output"), alias="OUTPUT_DIR_PATH")

    # --- Crossref API ---
    crossref_api_delay: float = 0.5
    crossref_api_email: EmailStr
    crossref_api_journals_url: HttpsUrlStr
    # Contains oject_name placeholder for issn
    crossref_api_journals_issn_url: UrlWithObjectName
    crossref_api_styles_url: HttpsUrlStr
    crossref_api_works_url: HttpsUrlStr
    crossref_api_works_get_limit: int = 20
    crossref_api_timeout: float = 20.0
    crossref_api_max_retry: int = 10

    # --- DOI Service ---
    doi_api_delay: float = 0.4
    doi_api_url: UrlWithObjectName  # Contains oject_name placeholder for doi
    doi_api_timeout: float = 10.0
    doi_api_max_retry: int = 10

    # --- Style Repositories ---
    style_repo_url: UrlWithObjectName  # Contains oject_name placeholder for style
    child_style_repo_url: UrlWithObjectName  # Contains template style
    all_styles_repo_url: HttpsUrlStr
    csl_xml_namespaces: dict[str, str]
    # Warning: csl_xml_namespaces with no HttpUrl type that Pydantic could alterate

    # --- Core Logic Settings ---
    context_keywords: str = ""
    journal_update_days: int = 30
    journal_update_limit: int = 100
    default_reference_style: str = "apa"

    # --- Values for schemas ---
    work_csl_schema_types: list[str] = Field(default_factory=list)

    # --- Blacklists & Cleaners ---
    parser_blacklist: list[str] = Field(default_factory=list)
    work_cls_schema_blacklist_fields: list[str] = Field(default_factory=list)
    author_cls_schema_blacklist_fields: list[str] = Field(default_factory=list)

    # HTML Cleaning Configuration
    # Structural tags to explicitly preserve in the local repository
    preserved_html_tags: set[str] = Field(default_factory=set)
    # Styling tags whose inner text is kept but boundaries are discarded
    discarded_html_tags: set[str] = Field(default_factory=set)

    # --- Directory Lifecycle Methods ---
    def ensure_repo_directory(self) -> None:
        """Create the validated local repository directory."""
        self.local_repo_dir_path.resolve().mkdir(parents=True, exist_ok=True)

    def ensure_output_directory(self) -> None:
        """Create the validated output directory."""
        self.output_dir_path.resolve().mkdir(parents=True, exist_ok=True)


def create_config(**kwargs: Any) -> AppConfig:
    """Instantiate a fresh configuration payload for runtime or isolation testing."""
    return AppConfig(**kwargs)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Retrieve the globally cached configuration configuration.
    WARNING: Should either be called in cli.py or inside class methods, not outside, so
    as to make tests not interfering with production directories."""
    return create_config()
