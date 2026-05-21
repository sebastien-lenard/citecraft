import logging
from unittest.mock import ANY, MagicMock, patch

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
    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
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
            progress_callback=ANY,
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

    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
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
            progress_callback=ANY,
        )


def test_cli_displays_journal_anomalies_warning_table(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Check if CLI catches metadata anomalies dictionary and correctly displays
    the updated warning text and multi-column status table.
    """
    mock_anomalies = {
        ("Natural Hazards", "1234-5678"): {
            "input_title": "Natural Hazards",
            "status": "Found without work",
            "issn": "1234-5678",
            "issns_found": "1234-5678, 9999-9999",
        },
        ("Unknown Fake Journal", None): {
            "input_title": "Unknown Fake Journal",
            "status": "Not found",
            "issn": "",
            "issns_found": "",
        },
    }

    mock_export = MagicMock()
    mock_export.total_rows = 0
    mock_export.output_filepath = "/mock/path.csv"

    with patch(
        "manuscript_reference_lister.cli.run",
        return_value=(mock_anomalies, mock_export),
    ):
        result = runner.invoke(
            cli,
            ["main", "-t", "Some text parsing context."],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        assert "Done." in result.output
        assert "or were found with at least one ISSN without works" in result.output
        assert (
            "These problematic titles or ISSNs have not been included" in result.output
        )

        # Check headers/columns of array
        assert "input_title" in result.output
        assert "issn" in result.output
        assert "status" in result.output
        assert "issns found" in result.output

        # Check content
        assert "Natural Hazards" in result.output
        assert "Found without work" in result.output
        assert "1234-5678" in result.output
        assert "1234-5678, 9999-9999" in result.output
        assert "Unknown Fake Journal" in result.output
        assert "Not found" in result.output


def test_progress_bar_disabled_in_verbose_mode(runner, test_config):
    """Check absence of progress bar if verbose option activated."""
    with (
        patch("manuscript_reference_lister.cli.run") as mock_run,
        patch("manuscript_reference_lister.cli.threading.Thread") as mock_thread,
    ):
        mock_run.return_value = ({}, {})

        result = runner.invoke(
            cli,
            ["main", "-f", "manuscript.docx", "-v"],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        mock_thread.assert_not_called()


def test_progress_bar_nominal_flow(runner, test_config):
    """Check nominal content of progress bar (0% à 100%)"""

    def mock_run_impl(
        input_file_path, input_text, output_filepath, config, progress_callback
    ):
        from manuscript_reference_lister.core import ProgressStep

        progress_callback(
            ProgressStep("parsing", 0, 4, "Parsing manuscript...", status="started")
        )
        progress_callback(
            ProgressStep(
                "references", 4, 4, "Bibliographic references saved", status="completed"
            )
        )
        return {}, {}

    with (
        patch("manuscript_reference_lister.cli.run", side_effect=mock_run_impl),
        patch("manuscript_reference_lister.cli.threading.Thread"),
        patch("time.time", side_effect=[1000.0, 1005.0, 1010.0]),
    ):
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

        assert result.exit_code == 0

        raw_output = result.output

        assert "\r\033[K" in raw_output or "\r\x1b[K" in raw_output

        assert "Bibliographic references saved" in raw_output
        assert "100%" in raw_output


def test_progress_bar_log_interruption_behavior(runner, test_config):
    """Check sequence when progress bar interrupted by a log"""

    def mock_run_with_log(
        input_file_path, input_text, output_filepath, config, progress_callback
    ):
        from manuscript_reference_lister.core import ProgressStep

        progress_callback(
            ProgressStep("parsing", 1, 4, "Step 1...", status="completed")
        )

        logger = logging.getLogger("manuscript_reference_lister.cli")
        logger.warning("Missing ISSN detected !")
        return {}, {}

    with (
        patch("manuscript_reference_lister.cli.run", side_effect=mock_run_with_log),
        patch("manuscript_reference_lister.cli.threading.Thread"),
        patch("time.time", return_value=1000.0),
    ):
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

        stderr_content = result.output  # Read Click capture

        assert "Missing ISSN detected !" in stderr_content

        # Display normalization if raw encoding replace \033 par \x1b
        stderr_content = stderr_content.replace("\x1b", "\033")
        parts = stderr_content.split("\033[K")

        log_sequence_found = False
        for i, part in enumerate(parts):
            if "Missing ISSN detected !" in part:
                assert "\n" in part

                # Following part that contains refreshed bar should display the step
                next_part = parts[i + 1]
                assert "Step 1..." in next_part
                log_sequence_found = True
                break

        assert log_sequence_found, (
            "The sequence [Erase -> Log -> Redraw] is not respected."
        )
