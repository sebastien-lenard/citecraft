# tests/unit/utils/test_config.py
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from citecraft.utils.config import create_config, get_config


@pytest.fixture
def base_raw_config() -> dict[str, Any]:
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


def test_db_filepath_computed_property(base_raw_config: dict[str, Any]) -> None:
    """Verify that the db_filepath property dynamically resolves using the repo path."""
    custom_repo = Path("/custom/repo/path")
    config = create_config(
        _env_file=None,
        LOCAL_REPO_DIR_PATH=custom_repo,
        DB_FILENAME="test_cache.db",
        **base_raw_config,
    )

    # Assert structural alignment between parts
    assert config.db_filepath == custom_repo / "test_cache.db"


def test_ensure_output_directory_creation(
    tmp_path: Path, base_raw_config: dict[str, Any],
) -> None:
    """Verify that ensure_output_directory creates the expected filesystem target."""
    test_output = tmp_path / "test_output"

    config = create_config(
        _env_file=None,
        OUTPUT_DIR_PATH=test_output,
        **base_raw_config,
    )

    assert not test_output.exists()
    config.ensure_output_directory()
    assert test_output.exists()


def test_get_config_global_cache_and_isolation(
    monkeypatch: pytest.MonkeyPatch, base_raw_config: dict[str, Any],
) -> None:
    """Verify get_config returns a cached singleton instance when evaluated."""
    # Since get_config reads environment variables / .env by default,
    # we mock the class initializer to return the mock config without reading disk.
    mock_config_instance = create_config(_env_file=None, **base_raw_config)

    # Track execution count using a wrapper spy
    call_count = 0

    def spy_create_config(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        nonlocal call_count
        call_count += 1
        return mock_config_instance

    monkeypatch.setattr("citecraft.utils.config.create_config", spy_create_config)

    # First access evaluates factory
    config_1 = get_config()
    # Second access pulls from lru_cache
    config_2 = get_config()

    assert config_1 is config_2
    assert call_count == 1  # Confirms lru_cache intercepted the second invocation
