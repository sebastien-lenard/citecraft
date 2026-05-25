from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from pydantic import EmailStr, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """.Env Configuration loader and validator. Don't load LOG_DIR_PATH, handled by
    logging_config.py"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Directory Paths ---
    local_repo_dir_path: Path = Field(default=Path("repo"), alias="LOCAL_REPO_DIR_PATH")
    output_dir_path: Path = Field(default=Path("output"), alias="OUTPUT_DIR_PATH")

    # --- Crossref API ---
    crossref_api_delay: float = 0.5
    crossref_api_email: EmailStr
    crossref_api_journals_url: HttpUrl
    crossref_api_journals_issn_url: str  # Contains template {issn}
    crossref_api_styles_url: HttpUrl
    crossref_api_works_url: HttpUrl
    crossref_api_works_get_limit: int = 20
    crossref_api_timeout: float = 20.0
    crossref_api_max_retry: int = 10

    # --- DOI Service ---
    doi_api_delay: float = 0.4
    doi_api_url: str  # Contains template {doi}
    doi_api_timeout: float = 10.0
    doi_api_max_retry: int = 10

    # --- Style Repositories ---
    style_repo_url: str  # Contains template {style}
    all_styles_repo_url: HttpUrl

    # --- Core Logic Settings ---
    context_keywords: str = ""
    journal_update_days: int = 30
    journal_update_limit: int = 100
    default_reference_style: str = "apa"

    # --- Blacklists & Cleaners ---
    parser_blacklist: list[str] = Field(
        default_factory=lambda: [
            "Fig",
            "Figs",
            "Figure",
            "Figures",
            "Tab",
            "Table",
            "Eq",
            "Plate",
            "Section",
            "See",
            "e.g.",
            "i.e.",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
    )

    work_cls_schema_blacklist_fields: list[str] = Field(
        default_factory=lambda: [
            "URL",
            "alternative-id",
            "assertion",
            "content-domain",
            "is-referenced-by-count",
            "license",
            "link",
            "member",
            "prefix",
            "reference",
            "reference-count",
            "references-count",
            "score",
            "source",
            "update-policy",
        ]
    )

    author_cls_schema_blacklist_fields: list[str] = Field(
        default_factory=lambda: [
            "ORCID",
            "affiliation",
            "authenticated-orcid",
            "role",
        ]
    )

    # HTML Cleaning Configuration
    # Structural tags to explicitly preserve in the local repository
    preserved_html_tags: set[str] = Field(default={"sup", "sub"})
    # Styling tags whose inner text is kept but boundaries are discarded
    discarded_html_tags: set[str] = Field(default={"i", "b", "strong", "u", "small"})

    # --- Advanced Pre-Validation (Before) ---
    @model_validator(mode="before")
    @classmethod
    def enforce_https_urls(cls, data: Any) -> Any:
        """Enforce and upgrade scheme to https:// for any field ending in _url."""
        if not isinstance(data, dict):
            return data

        updated_data = {**data}
        for key, value in updated_data.items():
            if key.lower().endswith("_url") and isinstance(value, str):
                val_str = value.strip()

                # Bypass empty targets or typical filesystem indicators
                if not val_str or val_str.startswith(("/", ".")):
                    continue

                # Handle malformed prefixing or absolute absence of scheme safely
                if val_str.startswith("://"):
                    val_str = f"https{val_str}"
                elif "://" not in val_str:
                    val_str = f"https://{val_str}"

                parsed = urlparse(val_str)

                if parsed.scheme == "http":
                    parsed = parsed._replace(scheme="https")
                    updated_data[key] = urlunparse(parsed)
                elif parsed.scheme == "https":
                    updated_data[key] = urlunparse(parsed)
                else:
                    raise ValueError(
                        f"Field '{key}' must use 'https://' scheme. Got unsupported: '{parsed.scheme}'"
                    )

        return updated_data

    # --- Structural Post-Validation (After) ---
    @field_validator("crossref_api_journals_issn_url", mode="after")
    @classmethod
    def validate_issn_template(cls, v: str) -> str:
        if "{issn}" not in v:
            raise ValueError("URL must contain the mandatory '{issn}' placeholder.")
        return v

    @field_validator("doi_api_url", mode="after")
    @classmethod
    def validate_doi_template(cls, v: str) -> str:
        if "{doi}" not in v:
            raise ValueError("URL must contain the mandatory '{doi}' placeholder.")
        return v

    @field_validator("style_repo_url", mode="after")
    @classmethod
    def validate_style_template(cls, v: str) -> str:
        if "{style}" not in v:
            raise ValueError("URL must contain the mandatory '{style}' placeholder.")
        return v

    # --- Directory Lifecycle Methods ---
    def ensure_repo_directory(self) -> None:
        """Create local repo directory."""
        self.local_repo_dir_path.mkdir(parents=True, exist_ok=True)

    def ensure_output_directory(self) -> None:
        """Create default output directory."""
        self.output_dir_path.mkdir(parents=True, exist_ok=True)


def create_config(**kwargs: Any) -> AppConfig:
    """Factory to always instantiate a fresh configuration payload (perfect for
    tests). Accepts Pydantic Settings kwargs (like _env_file) for testing isolation.
    """
    return AppConfig(**kwargs)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Gets current cached config or load it with validation.
    WARNING: Should either be called in cli.py or inside class methods, not outside, so
    as to make tests not interfering with production directories."""
    return create_config()
