# tests/unit/test_logging_config.py
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pythonjsonlogger.json import JsonFormatter

from citecraft.logging_config import (
    ColorFormatter,
    RunIdFilter,
    get_logging_config,
    setup_logging,
)


class TestRunIdFilter:
    def test_run_id_filter_injects_uuid(self) -> None:
        """Verify that RunIdFilter injects a run_id string into the LogRecord."""
        log_filter = RunIdFilter()
        mock_record = MagicMock(spec=logging.LogRecord)

        del mock_record.run_id

        result = log_filter.filter(mock_record)

        assert result is True
        assert hasattr(mock_record, "run_id")
        assert isinstance(mock_record.run_id, str)
        assert len(mock_record.run_id) == 8


class TestColorFormatter:
    @pytest.fixture
    def basic_record(self) -> logging.LogRecord:
        """Isolated LogRecord fixture for format testing."""
        return logging.LogRecord(
            name="citecraft.core.engine",
            level=logging.WARNING,
            pathname="engine.py",
            lineno=42,
            msg="Task processing slow",
            args=(),
            exc_info=None,
        )

    def test_color_formatter_applies_ansi_and_truncates_name(
        self, basic_record: logging.LogRecord
    ) -> None:
        """Verify ANSI escapes are injected and package prefixes are truncated."""
        formatter = ColorFormatter(fmt="%(name)s: %(message)s")
        formatted = formatter.format(basic_record)

        # Colors should be present (YELLOW for WARNING), line cleared, and reset applied
        assert ColorFormatter.CLEAR_LINE in formatted
        assert ColorFormatter.YELLOW in formatted
        assert ColorFormatter.RESET in formatted

        # Name should be truncated from citecraft.core.engine -> engine
        assert "engine: Task processing slow" in formatted
        assert basic_record.name == "citecraft.core.engine"  # Verify restoration

    def test_color_formatter_restores_name_on_formatting_exception(
        self, basic_record: logging.LogRecord
    ) -> None:
        """Edge Case: Ensure record.name restoration even if rendering throws error."""
        formatter = ColorFormatter(fmt="%(name)s: %(message)s")

        # Force an exception during formatting by mocking super().format
        with (
            patch(
                "logging.Formatter.format", side_effect=ValueError("Formatting failed")
            ),
            pytest.raises(ValueError, match="Formatting failed"),
        ):
            formatter.format(basic_record)

        # The try...finally block must have recovered the original namespace name
        assert basic_record.name == "citecraft.core.engine"


class TestLoggingConfigMatrix:
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
        self, verbose_level: int, expected_console_level: str
    ) -> None:
        """Verify that the console log level scales correctly with verbosity."""
        dummy_path = Path("/dummy/path")
        config = get_logging_config(dummy_path, verbose_level=verbose_level)

        assert config["handlers"]["console"]["level"] == expected_console_level
        assert config["handlers"]["file"]["filename"] == str(
            dummy_path / "app.json.log"
        )


class TestSetupLoggingLifecycles:
    # patch MUST point directly to the module consuming the function
    @patch("citecraft.logging_config.get_safe_dir")
    @patch("logging.config.dictConfig")
    def test_setup_logging_success(
        self, mock_dict_config: MagicMock, mock_get_dir: MagicMock
    ) -> None:
        """Verify successful initialization loop with proper 3-tuple path unpacking."""
        mock_path = Path("/mock/safe/dir")
        mock_get_dir.return_value = (mock_path, mock_path, False)

        log_dir, intended_dir, is_fallback = setup_logging(verbose_level=1)

        assert log_dir == mock_path
        assert intended_dir == mock_path
        assert is_fallback is False
        mock_dict_config.assert_called_once()

    @patch("citecraft.logging_config.get_safe_dir")
    @patch("logging.config.dictConfig")
    @patch("logging.basicConfig")
    def test_setup_logging_failure_fallback(
        self,
        mock_basic_config: MagicMock,
        mock_dict_config: MagicMock,
        mock_get_dir: MagicMock,
    ) -> None:
        """Edge Case: Verify hard crashes in dictConfig trigger stderr reports and
        basicConfig."""
        mock_path = Path("/mock/safe/dir")
        mock_get_dir.return_value = (mock_path, mock_path, True)

        # Simulate a component initialization failure (e.g., package missing or bad
        # structure)
        mock_dict_config.side_effect = ValueError("Invalid handler class configuration")

        with patch("sys.stderr.write"), patch("traceback.print_exc") as mock_traceback:
            log_dir, _, is_fallback = setup_logging(verbose_level=0)

            # We should successfully catch the error, log data to streams, and return
            # structural values
            assert is_fallback is True
            assert log_dir == mock_path
            mock_traceback.assert_called_once_with(file=sys.stderr)
            mock_basic_config.assert_called_once_with(
                level=logging.WARNING, stream=sys.stderr
            )


class TestStructuredJsonOutput:
    def test_json_formatter_outputs_valid_structured_data(self) -> None:
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

        for key in parsed_json:
            assert "%(" not in key, f"Detected unsolved placeholder in JSON key: {key}"
