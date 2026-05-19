from unittest.mock import patch

import pytest
from click.testing import CliRunner

from manuscript_reference_lister.cli import cli
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def runner() -> CliRunner:
    """Provides a Click CliRunner instance for testing CLI commands."""
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_setup_logging():
    """Autouse fixture to prevent the CLI from restructuring the global logging
    handlers and breaking pytest's caplog during global test suite runs.
    """

    with patch("manuscript_reference_lister.cli.setup_logging") as mock:
        mock.return_value = "/mock/log/dir"
        yield mock


def test_cli_success(runner: CliRunner, test_config: AppConfig) -> None:
    """Verify that the CLI exits with 0 on successful execution."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

        assert result.exit_code == 0
        assert "Done." in result.output
        mock_run.assert_called_once_with(
            input_file_path="manuscript.docx",
            input_text="",
            output_filepath=None,
            config=test_config,
        )


def test_cli_handles_unexpected_exception_and_exits_1(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that an unhandled exception in core.run causes the CLI to print
    an error message and exit with status code 1."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Database or File system corruption")

        result = runner.invoke(
            cli, ["main", "-f", "corrupted.docx"], obj={"config": test_config}
        )

        assert result.exit_code == 1
        assert (
            "Error: An unexpected error occurred: Database or File system corruption"
            in result.output
        )
        assert "--- Debug Traceback ---" not in result.output
        assert (
            "Use the '-v' or '-vv' option to see the full debug traceback."
            in result.output
        )


def test_cli_shows_traceback_in_verbose_mode(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that passing the verbose flag (-v) includes the debug traceback
    upon failure."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Network link completely broken")

        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx", "-v"], obj={"config": test_config}
        )

        assert result.exit_code == 1
        assert (
            "Error: An unexpected error occurred: Network link completely broken"
            in result.output
        )

        assert "--- Debug Traceback ---" in result.output
        assert "RuntimeError: Network link completely broken" in result.output
        assert "-----------------------" in result.output


def test_cli_piped_input_handling(runner: CliRunner, test_config: AppConfig) -> None:
    """Verify that standard input redirection (piping) passes the string
    correctly to the run function."""
    piped_text = "Some citation (Lenard et al., 2025)"

    with patch("manuscript_reference_lister.cli.run") as mock_run:
        result = runner.invoke(
            cli, ["main"], input=piped_text, obj={"config": test_config}
        )

        assert result.exit_code == 0
        assert "Done." in result.output
        mock_run.assert_called_once_with(
            input_file_path=None,
            input_text=piped_text,
            output_filepath=None,
            config=test_config,
        )


def test_cli_displays_journal_anomalies_warning_table(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Check if CLI catches metadata anomalies from run() and correctly displays
    the warnings and status table."""
    mock_anomalies = {
        "Natural Hazards and Earth System Sciences": "Found without ISSN",
        "Unknown Fake Journal": "Not found",
    }

    with patch("manuscript_reference_lister.cli.run", return_value=mock_anomalies):
        result = runner.invoke(
            cli,
            ["main", "-t", "Some text in nature geosciences."],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        assert "Done." in result.output
        assert "Warning: Some journal titles were not found" in result.output
        assert "This is a known limitation of the Crossref repository" in result.output
        assert "Natural Hazards and Earth System Sciences" in result.output
        assert "Found without ISSN" in result.output
        assert "Unknown Fake Journal" in result.output
        assert "Not found" in result.output
        assert "input_title" in result.output
        assert "status" in result.output
