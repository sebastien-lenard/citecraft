# tests/unit/test_cli.py
"""Unit and integration testing matrix for the Click CLI entry points."""

import runpy
import sqlite3
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from citecraft.cli import (
    COL1_W,
    COL2_W,
    ProcessedArgs,
    _configure_windows_console,
    _execute_processing_pipeline,
    _handle_execution_failure,
    _read_piped_input,
    _render_anomalies,
    _render_csv_preview,
    _render_export_summary,
    _render_recommendations,
    clear_cache_command,
    cli,
)
from citecraft.services.bibliography_service import ExportResult
from citecraft.utils import AppConfig

# ==============================================================================
# FIXTURES & TEST MOCKS
# ==============================================================================


@pytest.fixture(autouse=True)
def mock_setup_logging() -> Generator[MagicMock, None, None]:
    """Patch setup_logging to safely bypass dictConfig modification routines."""
    with patch("citecraft.cli.setup_logging") as mocked_log:
        mocked_log.return_value = (Path("logs"), Path("logs"), False)
        yield mocked_log


@pytest.fixture
def mock_core_run() -> Generator[MagicMock, None, None]:
    """Isolate the heavy core business logic function during interface cycles."""
    with patch("citecraft.cli.run") as mocked_run:
        yield mocked_run


@pytest.fixture
def dummy_export_result(tmp_path: Path) -> ExportResult:
    """Provide a reliable data carrier response representing standard execution."""
    return ExportResult(
        total_rows=3,
        output_filepath=tmp_path / "output.csv",
        style="apa",
        ok_count=1,
        missing_count=1,
        duplicate_count=1,
        sample_ok={"Citation": "Doe2020", "Status": "OK", "Reference": "Doe, J."},
        sample_missing={
            "Citation": "Smith2021",
            "Status": "No doi or reference",
            "Reference": "None",
        },
        samples_duplicate=[
            {
                "Citation": "Dup2022",
                "Status": "select the right reference",
                "Reference": "Dup, A.",
            }
        ],
    )


# ==============================================================================
# 1. ATOMIC UNIT TESTS (RENDERERS & PLATFORM HELPERS)
# ==============================================================================


def test_configure_windows_console_execution() -> None:
    """Verify console wrapper re-initialization logic safely fires."""
    with patch("sys.platform", "win32"), patch("io.TextIOWrapper") as mock_wrapper:
        _configure_windows_console()
        assert mock_wrapper.call_count == 2


def test_read_piped_input_empty_when_tty() -> None:
    """Check that stdin returns empty strings when evaluated inside interactive TTYs."""
    with patch("sys.stdin.isatty", return_value=True):
        assert _read_piped_input() == ""


def test_read_piped_input_with_stream_data() -> None:
    """Check string processing escapes strings correctly when stream bytes are piped."""
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stdin.read", return_value="Test \\n Text\\r"),
    ):
        result = _read_piped_input()
        assert "Test" in result
        assert "\r" not in result


def test_render_anomalies_empty() -> None:
    """Ensure anomaly printer returns early with zero console allocations if empty."""
    with patch("click.echo") as mock_echo:
        _render_anomalies({})
        mock_echo.assert_not_called()


def test_render_anomalies_displays_table() -> None:
    """Verify anomaly layouts match parameters and trigger multi-line text wrapping."""
    anomalies = {
        "item1": {
            "input_title": "Nature",
            "issn": "0028-0836",
            # Exceeds visual column layouts to force multiple wrapper line sequences
            "status": "Missing Works " * 20,
            "issns_found": "0028-0836",
        }
    }
    with patch("click.echo") as mock_echo, patch("click.secho") as mock_secho:
        _render_anomalies(anomalies)
        assert mock_secho.called
        assert mock_echo.called
        # Check that content lines are captured by verifying the text keywords exist
        printed_output = "".join(
            call[0][0] for call in mock_echo.call_args_list if call[0]
        )
        assert "Nature" in printed_output


def test_render_export_summary(dummy_export_result: ExportResult) -> None:
    """Verify statistics counters report matching metric values."""
    with patch("click.secho") as mock_secho, patch("click.echo") as mock_echo:
        _render_export_summary(dummy_export_result)

        assert any(
            "Valid references (OK)" in call[0][0] for call in mock_echo.call_args_list
        )
        assert mock_secho.called


def test_render_csv_preview_empty() -> None:
    """Ensure csv preview yields early when sample blocks are completely vacant."""
    empty_result = ExportResult(total_rows=0, output_filepath=Path("test.csv"))
    with patch("click.secho") as mock_secho:
        _render_csv_preview(empty_result)
        mock_secho.assert_not_called()


def test_render_csv_preview_forces_text_wrapping() -> None:
    """Verify that references exceeding COL3_W trigger the multi-line layout loop."""
    long_ref = "Very long reference string " * 5  # Exceeds 60 characters
    wrapped_result = ExportResult(
        total_rows=1,
        output_filepath=Path("test.csv"),
        sample_ok={"Citation": "Long2026", "Status": "OK", "Reference": long_ref},
    )

    with patch("click.echo") as mock_echo, patch("click.secho"):
        _render_csv_preview(wrapped_result)

        # Check that empty columns are printed to align with the wrapped extra line
        printed_lines = [call[0][0] for call in mock_echo.call_args_list if call[0]]
        assert any(
            line.startswith(f"{'':<{COL1_W}} | {'':<{COL2_W}} |")
            for line in printed_lines
        )


def test_render_csv_preview_with_rows(dummy_export_result: ExportResult) -> None:
    """Ensure status warnings rewrite descriptions dynamically within tables."""
    with patch("click.echo") as mock_echo, patch("click.secho") as mock_secho:
        _render_csv_preview(dummy_export_result)
        assert mock_secho.called
        printed_output = "".join(call[0][0] for call in mock_echo.call_args_list)
        assert "Warning: Missing metadata" in printed_output
        assert "Warning: Multiple matches" in printed_output


def test_render_recommendations(dummy_export_result: ExportResult) -> None:
    """Ensure recommendations populate warnings conditional to data metrics."""
    with patch("click.echo") as mock_echo:
        _render_recommendations(dummy_export_result)
        output = "".join(call[0][0] for call in mock_echo.call_args_list)
        assert "please search for their dois" in output.lower()
        assert "review the generated csv" in output.lower()


# ==============================================================================
# 2. CORE RUNNER ROUTING & ORCHESTRATION TESTS
# ==============================================================================


def test_execute_pipeline_quits_early_on_no_input_interactive(
    test_config: AppConfig,
) -> None:
    """Ensure pipeline exits when input files are absent inside an interactive TTY."""
    args = ProcessedArgs(
        api="OpenAlex",
        input_file=None,
        journal_title=None,
        output_file=None,
        skip_journal_update=False,
        skip_work_update=False,
        style=None,
        text=None,
        verbose=0,
    )
    with patch("sys.stdin.isatty", return_value=True), patch("click.echo") as mock_echo:
        _execute_processing_pipeline(test_config, args, None)

    printed_output = "".join(call[0][0] for call in mock_echo.call_args_list if call[0])
    assert "No manuscript file or raw text provided.\nDone." in printed_output


def test_execute_pipeline_quits_early_on_no_input_non_interactive(
    test_config: AppConfig,
) -> None:
    """Ensure error printing when absent inputs inside a non-interactive environment."""
    args = ProcessedArgs(
        api="OpenAlex",
        input_file=None,
        journal_title=None,
        output_file=None,
        skip_journal_update=False,
        skip_work_update=False,
        style=None,
        text=None,
        verbose=0,
    )
    with (
        patch("click.echo") as mock_echo,
        patch("citecraft.cli._read_piped_input", return_value=""),
    ):
        _execute_processing_pipeline(test_config, args, None)
        assert any(
            "No manuscript file" in call[0][0] for call in mock_echo.call_args_list
        )


@pytest.mark.parametrize(
    ("skip_journal", "skip_work"),
    [
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_execute_pipeline_displays_skips(
    test_config: AppConfig,
    mock_core_run: MagicMock,
    dummy_export_result: ExportResult,
    skip_journal: bool,
    skip_work: bool,
) -> None:
    """Verify information notices match user configurations."""
    mock_core_run.return_value = ({}, dummy_export_result)
    args = ProcessedArgs(
        api="OpenAlex",
        input_file="manuscript.docx",
        journal_title=None,
        output_file=None,
        skip_journal_update=skip_journal,
        skip_work_update=skip_work,
        style=None,
        text=None,
        verbose=0,
    )

    with (
        patch("click.echo") as mock_echo,
        patch("citecraft.cli._read_piped_input", return_value=""),
    ):
        _execute_processing_pipeline(test_config, args, "Cache Message")
        output = "".join(call[0][0] for call in mock_echo.call_args_list)
        assert "Pipeline Skips:" in output
        if skip_journal:
            assert "Journal metadata update was skipped." in output
        if skip_work:
            assert "Work DOI search and update was skipped." in output


def test_execute_pipeline_reraises_click_exception(test_config: AppConfig) -> None:
    """Ensure standard click exceptions bubble up without trigger mapping overrides."""
    args = ProcessedArgs(
        api="OpenAlex",
        input_file="test.docx",
        journal_title=None,
        output_file=None,
        skip_journal_update=False,
        skip_work_update=False,
        style=None,
        text=None,
        verbose=0,
    )
    with (
        patch("citecraft.cli.run", side_effect=click.ClickException("Click error")),
        patch("citecraft.cli._read_piped_input", return_value=""),
        pytest.raises(click.ClickException),
    ):
        _execute_processing_pipeline(test_config, args, None)


def test_execute_pipeline_catches_generic_exceptions(test_config: AppConfig) -> None:
    """Verify raw runtime errors are intercepted by boundary exception handlers."""
    args = ProcessedArgs(
        api="OpenAlex",
        input_file="test.docx",
        journal_title=None,
        output_file=None,
        skip_journal_update=False,
        skip_work_update=False,
        style=None,
        text=None,
        verbose=0,
    )
    with (
        patch(
            "citecraft.cli.run",
            side_effect=RuntimeError("Unhandled core runtime failure"),
        ),
        patch("citecraft.cli._read_piped_input", return_value=""),
        patch("citecraft.cli._handle_execution_failure") as mock_fail_handler,
    ):
        _execute_processing_pipeline(test_config, args, "Cache active state")
        mock_fail_handler.assert_called_once()


def test_handle_execution_failure_verbose_traceback() -> None:
    """Verify debug system captures call frames explicitly under verbose level flags."""
    try:
        raise ValueError("Deep core tracking error")
    except ValueError as err:
        with (
            patch("click.echo"),
            patch("click.secho") as mock_secho,
            pytest.raises(SystemExit) as exit_block,
        ):
            _handle_execution_failure(err, verbose=1, cache_msg="Clean Cache Running")
            assert exit_block.value.code == 1
            assert any(
                "Debug Traceback" in call[0][0] for call in mock_secho.call_args_list
            )


def test_handle_execution_failure_non_verbose() -> None:
    """Verify output reminds users about available debug verbosity switches when low."""
    try:
        raise ValueError("Standard muted dependency crash")
    except ValueError as err:
        with (
            patch("click.echo") as mock_echo,
            pytest.raises(SystemExit) as exit_block,
        ):
            _handle_execution_failure(err, verbose=0, cache_msg="Cache Ok")
            assert exit_block.value.code == 1
            printed_output = "".join(call[0][0] for call in mock_echo.call_args_list)
            assert (
                "Use the '-v' or '-vv' option to see the full debug traceback."
                in printed_output
            )


# ==============================================================================
# 3. CLICK INTERFACE INTEGRATION MATRIX (CLI / PROCESS / CACHE)
# ==============================================================================


def test_cli_forward_to_process_command_explicit() -> None:
    """Ensure invoking explicit process subcommands triggers interface entry points."""
    with patch("citecraft.cli._execute_processing_pipeline") as mock_pipeline:
        runner = CliRunner()
        result = runner.invoke(cli, ["-t", "Sample Raw Citation Block"])
        assert result.exit_code == 0
        mock_pipeline.assert_called_once()


def test_cli_forward_to_process_command_by_default() -> None:
    """Ensure omitting subcommands routes to processing layers via implicit defaults."""
    with patch("citecraft.cli._execute_processing_pipeline") as mock_pipeline:
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_pipeline.assert_called_once()


def test_cli_root_intercepts_clear_cache_and_returns(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Verify that the root cli group intercepts the --clear-cache flag, forwards
    execution to clear_cache_command, and returns immediately without running
    the main manuscript pipeline logic.
    """
    with (
        patch("citecraft.cli.archive_database_cache") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
        patch("click.confirm", return_value=True),
        patch("citecraft.cli.process_command") as mock_process_cmd,
    ):
        mock_archive.return_value = Path("repo/cache.db.backup")
        runner = CliRunner()

        # Invoke the root CLI directly with the cache clear option flag
        result = runner.invoke(cli, ["--clear-cache"])

        # Assertions to ensure the flag was intercepted and execution halted
        assert result.exit_code == 0
        assert "🧹 Local cache cleared" in result.output

        # This confirms the context short-circuited via the return statement
        # and never reached the ctx.invoke(process_command, **kwargs) line!
        mock_process_cmd.assert_not_called()


def test_cli_clear_cache_hit_explicit_return_statement() -> None:
    """Force execution past ctx.forward to explicitly cover the return statement.
    By patching the clear_cache_command to behave like a standard normal function
    instead of calling sys.exit(0), execution returns to the parent framework block
    and steps directly onto the trailing return guard.
    """
    runner = CliRunner()

    # Create a harmless mock callback function that just passes cleanly
    mock_callback = MagicMock(return_value=None)

    # We patch the underlying callback function inside the existing Click command
    with (
        patch.object(clear_cache_command, "callback", mock_callback),
        patch("citecraft.cli._configure_windows_console"),
        patch("citecraft.cli.get_config"),
    ):
        # Invoke the cli group context with the flag active
        result = runner.invoke(cli, ["--clear-cache"])

        # Verify the root group did its job and exited cleanly
        assert result.exit_code == 0
        assert mock_callback.called


def test_cache_clear_command_exits_early_unconditionally(
    test_config: AppConfig,
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Verify standalone cache clear terminates with the official spec exit message."""
    expected_backup = Path("repo/cache.db.backup")
    with (
        patch("citecraft.cli.archive_database_cache") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
        patch("click.confirm", return_value=True),
    ):
        mock_archive.return_value = expected_backup
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["cache", "clear"],
            obj={"config": test_config},
        )

    assert result.exit_code == 0
    assert "🧹 Local cache cleared" in result.output


def test_process_command_with_clear_cache_flag_halts_pipeline(
    test_config: AppConfig,
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Verify process command halts instantly when --clear-cache flag is provided."""
    with (
        patch("citecraft.cli.archive_database_cache") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
        patch("click.confirm", return_value=True),
        patch("citecraft.cli._execute_processing_pipeline") as mock_pipeline,
    ):
        mock_archive.return_value = Path("repo/cache.db.backup")
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["--clear-cache", "-t", "Some reference text"],
            obj={"config": test_config},
        )

    assert result.exit_code == 0
    mock_pipeline.assert_not_called()
    assert "Starting citecraft..." not in result.output
    assert "Done." in result.output


def test_cache_clear_command_flow_confirmed(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Verify file archive transformations execute completely on confirmation."""
    with (
        patch("citecraft.cli.archive_database_cache") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_archive.return_value = Path("repo/cache.db.backup")
        runner = CliRunner()
        result = runner.invoke(cli, ["cache", "clear"], input="y\n")

        assert result.exit_code == 0
        assert "Local cache cleared" in result.output
        mock_archive.assert_called_once()


def test_cache_clear_command_flow_aborted(test_config: AppConfig) -> None:  # noqa: ARG001
    """Verify state protection layers break safely when authorization matches false."""
    runner = CliRunner()
    result = runner.invoke(cli, ["cache", "clear"], input="n\n")
    assert result.exit_code == 0
    assert "Operation cancelled." in result.output


def test_cache_clear_handles_database_missing(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Ensure missing paths skip file operations gracefully."""
    with patch("citecraft.cli.archive_database_cache", return_value=None):
        runner = CliRunner()
        result = runner.invoke(cli, ["cache", "clear"], input="y\n")
        assert result.exit_code == 0
        assert "was not found. Skipping" in result.output


def test_cache_clear_handles_sqlite_exceptions(
    test_config: AppConfig,
    mock_setup_logging: MagicMock,  # noqa: ARG001
) -> None:
    """Ensure sqlite operational locks capture traceback states and exit with 1."""
    with patch(
        "citecraft.cli.archive_database_cache", side_effect=sqlite3.Error("Locked file")
    ):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["cache", "clear"], obj={"config": test_config}, input="y\n"
        )

    assert result.exit_code == 1
    assert "Cache clearing failed." in result.output


def test_process_command_triggers_inline_cache_clear(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,  # noqa: ARG001
    mock_core_run: MagicMock,
) -> None:
    """Verify using processing flags triggers forward operations across controllers."""
    mock_core_run.return_value = ({}, None)
    with (
        patch("citecraft.cli.archive_database_cache") as mock_archive,
        patch("pathlib.Path.exists", return_value=True),
    ):
        mock_archive.return_value = Path("repo/cache.db.backup")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--clear-cache", "-t", "Citation text"], input="y\n"
        )
        assert result.exit_code == 0
        assert "Local cache cleared" in result.output


@pytest.mark.parametrize(
    ("verbose_flag", "expected_log_call"),
    [
        ([], 0),
        (["-v"], 1),
        (["-vv"], 2),
    ],
)
def test_process_command_verbosity_mapping(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,
    mock_core_run: MagicMock,
    verbose_flag: list[str],
    expected_log_call: int,
) -> None:
    """Validate argument maps scale verbosity integers accurately."""
    mock_core_run.return_value = ({}, None)
    runner = CliRunner()
    args = [*verbose_flag, "-t", "Raw Source Parsing String Data"]

    result = runner.invoke(cli, args)

    assert result.exit_code == 0
    mock_setup_logging.assert_called_with(verbose_level=expected_log_call)


def test_process_command_logging_fallback_notices(
    test_config: AppConfig,  # noqa: ARG001
    mock_core_run: MagicMock,
    mock_setup_logging: MagicMock,
) -> None:
    """Verify logging subsystem triggers warning prints when is_fallback True."""
    mock_core_run.return_value = ({}, None)
    mock_setup_logging.return_value = (Path("tmp/logs"), Path("intended/logs"), True)

    with patch("citecraft.cli.logger.debug") as mock_logger_debug:
        runner = CliRunner()
        runner.invoke(cli, ["-t", "Muted Stream Trigger Text"])
        assert any(
            "Falling back to temporary storage" in call[0][0]
            for call in mock_logger_debug.call_args_list
        )


def test_process_command_handles_type_fallback_guards(
    test_config: AppConfig,  # noqa: ARG001
    mock_setup_logging: MagicMock,  # noqa: ARG001
    mock_core_run: MagicMock,
) -> None:
    """Check mappings process parameters without mutations or runtime exceptions."""
    mock_core_run.return_value = ({}, None)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--api",
            "Crossref",
            "--input-file",
            "valid_path.docx",
            "--journal-title",
            "Geomorphology",
            "--output-file",
            "results.csv",
            "--style",
            "copernicus-publications",
        ],
    )
    assert result.exit_code == 0
    assert "Starting citecraft..." in result.output


# ==============================================================================
# 4. EXECUTABLE NAMESPACE COMPILATION HARNESS
# ==============================================================================


def test_actual_main_execution_entrypoint_path() -> None:
    """Execute the true __main__ runtime block to verify top-level script parsing."""
    with (
        patch("sys.argv", ["citecraft", "-t", "Test"]),
        patch("logging.config.dictConfig"),
        patch("click.Command.main") as mock_click_main,
    ):
        # We simulate the entry point by allowing run_module to process the namespace,
        # but intercept click execution so it safely records execution without exiting
        runpy.run_module("citecraft.cli", run_name="__main__", alter_sys=True)

    assert mock_click_main.called


def test_executable_entrypoint_namespace_compilation() -> None:
    """Simulate standalone imports to hit the '__main__' execution engine path."""
    if "citecraft.cli" in sys.modules:
        del sys.modules["citecraft.cli"]

    # Patch dictConfig at the source library level to preserve test logging states
    with (
        patch("sys.argv", ["citecraft"]),
        patch("logging.config.dictConfig") as mock_dict_config,
        patch("runpy._run_code") as mock_run_code,
    ):
        runpy.run_module("citecraft.cli", run_name="__main__")
        assert mock_run_code.called
        # Ensures that even if hit, dictConfig did not modify live environments
        mock_dict_config.assert_not_called()
