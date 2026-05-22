import logging
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from click.testing import CliRunner

from manuscript_reference_lister.cli import cli
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def test_config() -> AppConfig:
    """Provides a controlled configuration instance for testing,
    ensuring complete isolation from local production .env files.
    """
    config = MagicMock(spec=AppConfig)
    config.default_reference_style = "apa"
    config.ensure_repo_directory = MagicMock()
    return config


@pytest.fixture
def fake_cache_env(test_config: AppConfig, tmp_path: Path) -> tuple[Path, list[Path]]:
    """Create temporary local repository files."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()

    test_config.local_repo_dir_path = str(repo_dir)

    cache_files = [repo_dir / "journal_records.json", repo_dir / "work_records.json"]

    for file in cache_files:
        file.write_text('{"test": "data"}', encoding="utf-8")

    return repo_dir, cache_files


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
            style="apa",
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


def test_cli_piped_input_default_style(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that standard input redirection (piping) passes the string
    correctly and uses the default style from the configuration."""
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
            style="apa",
            progress_callback=ANY,
        )


def test_cli_custom_style_and_output_options(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that both --style and --output_file options correctly propagate
    their values to the core.run function.
    """
    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli,
            [
                "main",
                "-f",
                "doc.docx",
                "-o",
                "custom_output.csv",
                "-s",
                "copernicus-publications",
            ],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            input_file_path="doc.docx",
            input_text="",
            output_filepath="custom_output.csv",
            config=test_config,
            style="copernicus-publications",
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


def test_progress_bar_disabled_in_verbose_mode(
    runner: CliRunner, test_config: AppConfig
) -> None:
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


def test_progress_bar_nominal_flow(runner: CliRunner, test_config: AppConfig) -> None:
    """Check nominal content of progress bar (0% à 100%)"""

    def mock_run_impl(
        input_file_path, input_text, output_filepath, config, style, progress_callback
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


def test_progress_bar_log_interruption_behavior(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Check sequence when progress bar interrupted by a log."""

    def mock_run_with_log(
        input_file_path, input_text, output_filepath, config, style, progress_callback
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


def test_cli_fatal_error_handling_cleans_progress_bar(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Check that fatal error triggers clean stop of the progress bar thread and the
    injection of an end of line to prevent visual collisions on stderr."""

    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Simulated database corruption")

        result = runner.invoke(
            cli, ["main", "-f", "dummy.docx"], obj={"config": test_config}
        )

        assert result.exit_code == 1
        assert (
            "Error: An unexpected error occurred: Simulated database corruption"
            in result.stderr
            or result.output
        )

        assert "\n" in (result.stderr or result.output), (
            "Crash did not trigger progress bar line freeing with end of line."
        )


def test_cli_clear_cache_option_absent_does_not_touch_files(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Checks that without option --clear-cache, files are untouched."""
    _, cache_files = fake_cache_env

    with patch("manuscript_reference_lister.cli.run", return_value=({}, {})):
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

    assert result.exit_code == 0
    for file in cache_files:
        assert file.exists()
        assert "bak_" not in result.output


def test_cli_clear_cache_cancelled_by_user(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Checks clear cache operation stops on user refusal."""
    _, cache_files = fake_cache_env

    result = runner.invoke(
        cli, ["main", "--clear-cache"], input="n\n", obj={"config": test_config}
    )

    assert result.exit_code == 0
    assert "Operation cancelled. Cache left untouched." in result.output

    for file in cache_files:
        assert file.exists()


def test_cli_clear_cache_maintenance_only_success(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Check maintenance mode: clear cache without handling manuscript/document."""
    repo_dir, cache_files = fake_cache_env

    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.return_value = ({}, {})

        result = runner.invoke(
            cli, ["main", "--clear-cache"], input="y\n", obj={"config": test_config}
        )

    assert result.exit_code == 0
    assert "Local cache cleared" in result.output
    assert "Done." in result.output

    for file in cache_files:
        assert not file.exists()

    backups = list(repo_dir.glob("*.bak_*"))
    assert len(backups) == 2


def test_cli_clear_cache_then_proceeds_to_run(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Check cache clearing followed by processing if input document present."""
    repo_dir, cache_files = fake_cache_env

    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli,
            ["main", "-f", "manuscript.docx", "--clear-cache"],
            input="y\n",
            obj={"config": test_config},
        )

    assert result.exit_code == 0
    assert "Local cache cleared" in result.output
    assert "Proceeding to manuscript processing with a fresh cache..." in result.output
    assert "Done." in result.output

    for file in cache_files:
        assert not file.exists()
    assert len(list(repo_dir.glob("*.bak_*"))) == 2

    mock_run.assert_called_once()


def test_cli_clear_cache_summary_displayed_at_the_very_end(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Check presence of cache clearing synthetic message after processing."""
    _, _ = fake_cache_env

    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli,
            ["main", "-f", "manuscript.docx", "--clear-cache"],
            input="y\n",
            obj={"config": test_config},
        )

    assert result.exit_code == 0
    mock_run.assert_called_once()

    lines = [line.strip() for line in result.output.splitlines() if line.strip()]

    assert any("🧹 Local cache cleared" in line for line in lines)

    # Check structure of the end of the output to ensure message hasn't been
    # erased/hidden
    assert "Done." in lines[-1]


def test_cli_clear_cache_partial_files_shows_warning(
    runner: CliRunner, test_config: AppConfig, fake_cache_env: tuple[Path, list[Path]]
) -> None:
    """Check that a warning is displayed if one of the expected cache files is missing."""
    _, cache_files = fake_cache_env

    missing_file = cache_files[0]
    missing_file.unlink()

    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.return_value = ({}, {})

        result = runner.invoke(
            cli, ["main", "--clear-cache"], input="y\n", obj={"config": test_config}
        )

    assert result.exit_code == 0
    assert (
        f"Warning: Expected cache file '{missing_file.name}' was not found"
        in result.output
    )
    assert "Moved: work_records.json" in result.output
    assert "Local cache cleared (1 file(s) safely archived" in result.output
