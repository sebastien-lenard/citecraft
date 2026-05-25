from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def ensure_directories(self) -> None:
    """Create directories explicitly."""
    self.local_repo_dir_path.mkdir(parents=True, exist_ok=True)
    self.output_dir_path.mkdir(parents=True, exist_ok=True)


class AppConfig(BaseSettings):
    """.Env Configuration loader and validator. Don't load LOG_DIR_PATH, handled by
    logging_config.py"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    local_repo_dir_path: Path = Field(default=Path("repo"), alias="LOCAL_REPO_DIR_PATH")
    output_dir_path: Path = Field(default=Path("output"), alias="OUTPUT_DIR_PATH")

    # Crossref API
    crossref_api_delay: float = 0.5
    crossref_api_email: EmailStr
    crossref_api_journals_url: HttpUrl
    crossref_api_journals_issn_url: str  # String because contains template {issn}
    crossref_api_styles_url: HttpUrl
    crossref_api_works_url: HttpUrl
    crossref_api_works_get_limit: int = 20
    crossref_api_timeout: float = 20.0
    crossref_api_max_retry: int = 10

    # DOI Service
    doi_api_delay: float = 0.4
    doi_api_url: str
    doi_api_timeout: float = 10.0
    doi_api_max_retry: int = 10

    # Style repo
    style_repo_url: str

    # Other Logic
    context_keywords: str = ""
    journal_update_days: int = 30
    journal_update_limit: int = 100

    default_reference_style: str = "apa"

    # Blacklist
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

    def ensure_repo_directory(self) -> None:
        """Create local repo directory."""
        self.local_repo_dir_path.mkdir(parents=True, exist_ok=True)

    def ensure_output_directory(self) -> None:
        """Create default output directory."""
        self.output_dir_path.mkdir(parents=True, exist_ok=True)


def create_config() -> AppConfig:
    """Factory to always create a fresh configuration instance (perfect for tests)."""
    return AppConfig()


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Gets current cached config or load it with validation.
    WARNING: Should either be called in cli.py or inside class methods, not outside, so
    as to make tests not interfering with production directories."""
    return create_config()
