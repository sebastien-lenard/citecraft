# src/citecraft/utils/config.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Citecraft environment configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import EmailStr, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from citecraft.schemas import (
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
        env_nested_delimiter="__",
    )

    # -------------------------------------------- #
    # USER'S CONFIGURATION                         #
    # -------------------------------------------- #

    # --- User's Directory Paths ---
    local_repo_dir_path: Path = Field(default=Path("repo"), alias="LOCAL_REPO_DIR_PATH")
    output_dir_path: Path = Field(default=Path("output"), alias="OUTPUT_DIR_PATH")
    # Warning: log_dir_path is handled in logging_config.py.

    # --- User's API Polite Pool email ---
    user_email: EmailStr

    # --- User's OpenAlex API Key ---
    openalex_api_key: str

    # -------------------------------------------- #
    # OTHER VARIABLES                              #
    # -------------------------------------------- #

    # --- Filepaths ---
    db_filename: str = Field(default="cache.db", alias="DB_FILENAME")

    # --- Default API calls ---

    default_api_key: str | None = None
    default_api_delay: float = 0.5
    default_api_timeout: float = 20
    default_api_max_retry: int = 10
    default_api_url_max_character_length: int = 2048

    # --- Crossref API ---
    crossref_api_journals_url: HttpsUrlStr
    # Contains oject_name placeholder for issn
    crossref_api_journals_issn_url: UrlWithObjectName
    crossref_api_styles_url: HttpsUrlStr
    crossref_api_works_url: HttpsUrlStr
    crossref_api_works_get_limit: int = 20

    crossref_api_key: str | None = None
    crossref_api_delay: float = default_api_delay
    crossref_api_timeout: float = default_api_timeout
    crossref_api_max_retry: int = default_api_max_retry
    crossref_api_url_max_character_length: int = default_api_url_max_character_length

    # --- DOI Service ---
    doi_api_url: UrlWithObjectName  # Contains oject_name placeholder for doi

    # Default API configuration used for DOI Service

    # --- OpenAlex API ---
    openalex_api_works_url: HttpsUrlStr
    openalex_api_works_get_limit: int = 100

    openalex_api_delay: float = default_api_delay
    openalex_api_timeout: float = default_api_timeout
    openalex_api_max_retry: int = default_api_max_retry
    openalex_api_url_max_character_length: int = default_api_url_max_character_length
    openalex_api_url_max_character_length_for_issns_filter: int = 50
    openalex_api_max_piped_filters: int = 100

    # --- Style Repositories ---
    style_repo_url: UrlWithObjectName  # Contains oject_name placeholder for style
    child_style_repo_url: UrlWithObjectName  # Contains template style
    all_styles_repo_url: HttpsUrlStr
    csl_xml_namespaces: dict[str, str]
    # Warning: csl_xml_namespaces with no HttpUrl type that Pydantic could alterate

    # --- Core Logic Settings ---
    min_publication_year: int = 1600
    max_publication_year: int = 2099
    max_count_of_authors_in_citation: int = 2
    context_keywords: str = ""
    journal_update_days: int = 30
    journal_update_limit: int = 100
    default_reference_style: str = "apa"
    default_logging_frequency_for_batch_updates: float = 10.0

    # --- Values for schemas ---
    work_csl_schema_types: list[str] = Field(default_factory=list)

    # --- Blacklists & Cleaners ---
    parser_blacklist: list[str] = Field(default_factory=list)
    work_crossref_schema_blacklist_fields: list[str] = Field(default_factory=list)
    author_crossref_schema_blacklist_fields: list[str] = Field(default_factory=list)
    work_openalex_schema_blacklist_fields: list[str] = Field(default_factory=list)
    author_openalex_schema_blacklist_fields: list[str] = Field(default_factory=list)

    # HTML Cleaning Configuration
    # Structural tags to explicitly preserve in the local repository
    preserved_html_tags: set[str] = Field(default_factory=set)
    # Styling tags whose inner text is kept but boundaries are discarded
    discarded_html_tags: set[str] = Field(default_factory=set)

    @computed_field
    @property
    def db_filepath(self) -> Path:
        """Dynamically construct the db filepath once repo path is resolved."""
        return self.local_repo_dir_path / self.db_filename

    # --- Directory Lifecycle Methods ---
    def ensure_repo_directory(self) -> None:
        """Create the validated local repository directory."""
        self.local_repo_dir_path.resolve().mkdir(parents=True, exist_ok=True)

    def ensure_output_directory(self) -> None:
        """Create the validated output directory."""
        self.output_dir_path.resolve().mkdir(parents=True, exist_ok=True)


def create_config(**kwargs: Any) -> AppConfig:  # noqa: ANN401
    """Instantiate a fresh configuration payload for runtime or isolation testing."""
    return AppConfig(**kwargs)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Retrieve the globally cached configuration configuration.

    WARNING: Should either be called in cli.py or inside class methods, not outside, so
    as to make tests not interfering with production directories.
    """
    return create_config()
