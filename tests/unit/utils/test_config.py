from pathlib import Path

import pytest
from pydantic import ValidationError

from citecraft.utils.config import create_config


@pytest.fixture
def base_raw_config() -> dict:
    """Base raw dictionary representing perfect, valid .env strings."""
    return {
        "user_email": "test@example.com",
        "openalex_api_key": "test_openalex_key",
        "openalex_api_works_url": "https://example.com/works",
        "crossref_api_journals_url": "https://example.com",
        "crossref_api_journals_issn_url": "https://example.com{object_name}",
        "crossref_api_styles_url": "https://example.com",
        "crossref_api_works_url": "https://example.com",
        "doi_api_url": "https://example.com{object_name}",
        "style_repo_url": "https://example.com{object_name}",
        "all_styles_repo_url": "https://example.com",
        "child_style_repo_url": "https://example.com{object_name}",
        "csl_xml_namespaces": {"cs": "http://citationstyles.org"},
        "parser_blacklist": ["Fig", "Figs"],
    }


def test_app_config_happy_path(base_raw_config: dict) -> None:
    """Verify that a valid configuration payload loads and converts smoothly."""
    config = create_config(_env_file=None, **base_raw_config)

    assert config.user_email == "test@example.com"
    assert config.openalex_api_key == "test_openalex_key"
    assert config.csl_xml_namespaces == {"cs": "http://citationstyles.org"}
    assert config.parser_blacklist == ["Fig", "Figs"]


def test_app_config_missing_required_fields(base_raw_config: dict) -> None:
    """Verify that missing a required field forces a ValidationError."""
    base_raw_config.pop("user_email")

    with pytest.raises(ValidationError) as exc_info:
        create_config(_env_file=None, **base_raw_config)

    assert "user_email" in str(exc_info.value)


def test_ensure_directories_creation(tmp_path: Path, base_raw_config: dict) -> None:
    """Verify system path side-effects operate properly using tmp_path."""
    test_repo = tmp_path / "test_repo"

    config = create_config(
        _env_file=None,
        LOCAL_REPO_DIR_PATH=str(test_repo),
        OUTPUT_DIR_PATH=str(tmp_path / "test_output"),
        **base_raw_config,
    )

    assert not test_repo.exists()
    config.ensure_repo_directory()
    assert test_repo.exists()
