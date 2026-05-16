from unittest.mock import patch

import pytest
from click.testing import CliRunner

from manuscript_reference_lister.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Provides a Click CliRunner instance for testing CLI commands."""
    return CliRunner()


def test_cli_success(runner: CliRunner) -> None:
    """Verify that the CLI exits with 0 on successful execution."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        result = runner.invoke(main, ["-f", "manuscript.docx"])

        assert result.exit_code == 0
        assert "Done." in result.output
        mock_run.assert_called_once_with(
            input_file_path="manuscript.docx", input_text="", output_filepath=None
        )


def test_cli_handles_unexpected_exception_and_exits_1(runner: CliRunner) -> None:
    """Verify that an unhandled exception in core.run causes the CLI to print
    an error message and exit with status code 1."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Database or File system corruption")

        result = runner.invoke(main, ["-f", "corrupted.docx"])

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


def test_cli_shows_traceback_in_verbose_mode(runner: CliRunner) -> None:
    """Verify that passing the verbose flag (-v) includes the debug traceback
    upon failure."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Network link completely broken")

        result = runner.invoke(main, ["-f", "manuscript.docx", "-v"])

        assert result.exit_code == 1
        assert (
            "Error: An unexpected error occurred: Network link completely broken"
            in result.output
        )

        assert "--- Debug Traceback ---" in result.output
        assert "RuntimeError: Network link completely broken" in result.output
        assert "-----------------------" in result.output


def test_cli_piped_input_handling(runner: CliRunner) -> None:
    """Verify that standard input redirection (piping) passes the string
    correctly to the run function."""
    piped_text = "Some citation (Lenard et al., 2025)"

    with patch("manuscript_reference_lister.cli.run") as mock_run:
        result = runner.invoke(main, input=piped_text)

        assert result.exit_code == 0
        assert "Done." in result.output
        mock_run.assert_called_once_with(
            input_file_path=None, input_text=piped_text, output_filepath=None
        )
