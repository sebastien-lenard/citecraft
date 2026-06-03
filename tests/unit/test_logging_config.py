import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pythonjsonlogger.json import JsonFormatter

from citecraft.logging_config import (
    RunIdFilter,
    get_logging_config,
    get_safe_log_dir,
    setup_logging,
)


def test_run_id_filter_injects_uuid() -> None:
    """Verify that RunIdFilter injects a run_id string into the LogRecord."""
    log_filter = RunIdFilter()
    mock_record = MagicMock(spec=logging.LogRecord)

    assert not hasattr(mock_record, "run_id")

    result = log_filter.filter(mock_record)

    assert result is True
    assert hasattr(mock_record, "run_id")
    assert isinstance(mock_record.run_id, str)
    assert len(mock_record.run_id) == 8


@pytest.mark.parametrize(
    "mock_env_values, expected_path_callable",
    [
        # Scenario A: Missing env variables -> Fallback to temporary directory subfolder
        (
            {},
            lambda: Path(tempfile.gettempdir()) / "manuscript-reference-lister",
        ),
        # Scenario B: Custom log directory path defined in the .env configuration
        (
            {"LOG_DIR_PATH": '"C:\\Custom\\Log\\Path"'},
            lambda: Path("C:\\Custom\\Log\\Path"),
        ),
    ],
)
def test_get_safe_log_dir_scenarios(
    mock_env_values: dict[str, str],
    expected_path_callable: Callable[[], Path],
) -> None:
    """Verify log path resolution fallback and custom extraction behaviors."""
    with patch(
        "citecraft.logging_config.dotenv_values",
        return_value=mock_env_values,
    ):
        log_dir = get_safe_log_dir()
        assert log_dir == expected_path_callable()


@pytest.mark.parametrize(
    "verbose_level, expected_console_level",
    [
        (0, "WARNING"),
        (1, "INFO"),
        (2, "DEBUG"),
        (3, "DEBUG"),
    ],
)
def test_get_logging_config_levels(
    verbose_level: int, expected_console_level: str
) -> None:
    """Verify that the console log level scales correctly with verbosity."""
    dummy_path = Path("/dummy/path")
    config = get_logging_config(dummy_path, verbose_level=verbose_level)

    assert config["handlers"]["console"]["level"] == expected_console_level
    assert config["handlers"]["file"]["filename"] == str(dummy_path / "app.json.log")


def test_setup_logging_creates_directory_and_calls_dictconfig() -> None:
    """Verify that setup_logging triggers directory creation and passes configuration
    to dictConfig."""
    with (
        patch("citecraft.logging_config.get_safe_log_dir") as mock_get_dir,
        patch("pathlib.Path.mkdir"),
        patch("logging.config.dictConfig") as mock_dict_config,
    ):
        mock_path = MagicMock(spec=Path)
        mock_get_dir.return_value = mock_path

        setup_logging(verbose_level=1)

        mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_dict_config.assert_called_once()


def test_json_formatter_outputs_valid_structured_data() -> None:
    """Verify that the JSON formatter properly extracts and maps log variables."""
    dummy_path = Path("/dummy/path")
    config = get_logging_config(dummy_path, verbose_level=1)
    formatter_spec = config["formatters"]["json"]

    formatter = JsonFormatter(
        fmt=formatter_spec["fmt"], rename_fields=formatter_spec["rename_fields"]
    )
    record = logging.LogRecord(
        name="citecraft.http",
        level=logging.INFO,
        pathname="api.py",
        lineno=10,
        msg="HTTP request sent",
        args=(),
        exc_info=None,
    )
    record.run_id = "ca6e29ed"

    formatted_output = formatter.format(record)
    parsed_json = json.loads(formatted_output)

    assert isinstance(parsed_json, dict)
    assert "timestamp" in parsed_json
    assert parsed_json["level"] == "INFO"
    assert parsed_json["run_id"] == "ca6e29ed"
    assert parsed_json["message"] == "HTTP request sent"

    for key in parsed_json.keys():
        assert "%(" not in key, f"Detected unsolved placeholder in JSON key: {key}"
