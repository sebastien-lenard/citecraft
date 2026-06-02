# tests/unit/test_cli.py
from collections.abc import Generator
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from click.testing import CliRunner

from manuscript_reference_lister.cli import cli
from manuscript_reference_lister.services.bibliography_service import ExportResult
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def test_local_repo_filepath(test_config: AppConfig, tmp_path: Path) -> Path:
    """Create temporary local repository cache database inside the directory."""
    db_path = Path(test_config.db_filepath).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("dummy database cache file", encoding="utf-8")
    return db_path


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CliRunner instance for CLI invocation tests."""
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_setup_logging() -> Generator[MagicMock, None, None]:
    """Isolate CLI tests from modifying global root log configurations."""
    with patch("manuscript_reference_lister.cli.setup_logging") as mock:
        mock.return_value = "/mock/log/dir"
        yield mock


def test_cli_success(runner: CliRunner, test_config: AppConfig) -> None:
    """Verify that the CLI exits with 0 on successful execution runs."""
    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

        assert result.exit_code == 0
        assert "Done." in result.output
        mock_run.assert_called_once_with(
            api="OpenAlex",
            input_file_path="manuscript.docx",
            input_text="",
            output_filepath=None,
            config=test_config,
            style="apa",
            journal_title=None,
            progress_callback=ANY,
            skip_journal_update=False,
            skip_work_update=False,
        )


def test_cli_journal_title_option_propagates(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that the -j option is correctly propagated to the pipeline."""
    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli,
            ["main", "-f", "manuscript.docx", "-j", "Geomorphology"],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            api="OpenAlex",
            input_file_path="manuscript.docx",
            input_text="",
            output_filepath=None,
            config=test_config,
            style="apa",
            journal_title="Geomorphology",
            progress_callback=ANY,
            skip_journal_update=False,
            skip_work_update=False,
        )


def test_cli_success_message_includes_resolved_style(
    runner: CliRunner,
    test_config: AppConfig,
) -> None:
    """Verify that success message contains the resolved style name."""
    mock_export_metadata = ExportResult(
        total_rows=3,
        output_filepath=Path("/mock/path/references.csv"),
        export_format="CSV",
        style="copernicus-publications",
    )

    with patch(
        "manuscript_reference_lister.cli.run",
        return_value=((), mock_export_metadata),
    ):
        result = runner.invoke(
            cli,
            ["main", "-t", "Some citation text.", "-s", "copernicus-publications"],
            obj={"config": test_config},
        )
        assert result.exit_code == 0
        assert (
            "Success: Generated and saved bibliography (copernicus-publications)"
            " with 3 rows"
        ) in result.output


@pytest.mark.parametrize(
    "verbose_args, expect_traceback",
    [
        # Scenario A: Standard error reporting without traceback output
        ([], False),
        # Scenario B: Verbose error reporting containing debug traceback details
        (["-v"], True),
    ],
)
def test_cli_exception_handling_paths(
    runner: CliRunner,
    test_config: AppConfig,
    verbose_args: list[str],
    expect_traceback: bool,
) -> None:
    """Verify that unexpected pipeline crashes are caught with traceback options."""
    with patch("manuscript_reference_lister.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("Database or File system corruption")

        result = runner.invoke(
            cli,
            ["main", "-f", "corrupted.docx", *verbose_args],
            obj={"config": test_config},
        )

        assert result.exit_code == 1
        assert (
            "Error: An unexpected error occurred: Database or File system corruption"
            in result.output
        )

        if expect_traceback:
            assert "--- Debug Traceback ---" in result.output
            assert "RuntimeError: Database or File system corruption" in result.output
        else:
            assert "--- Debug Traceback ---" not in result.output
            assert (
                "Use the '-v' or '-vv' option to see the full debug traceback."
                in result.output
            )


def test_cli_piped_input_default_style(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify standard input redirection forwards strings correctly using defaults."""
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
            api="OpenAlex",
            input_file_path=None,
            input_text=piped_text,
            output_filepath=None,
            config=test_config,
            style="apa",
            journal_title=None,
            progress_callback=ANY,
            skip_journal_update=False,
            skip_work_update=False,
        )


def test_cli_custom_style_and_output_options(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify custom styles and output paths are propagated cleanly to pipelines."""
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
            api="OpenAlex",
            input_file_path="doc.docx",
            input_text="",
            output_filepath="custom_output.csv",
            config=test_config,
            style="copernicus-publications",
            journal_title=None,
            progress_callback=ANY,
            skip_journal_update=False,
            skip_work_update=False,
        )


def test_cli_skip_update_flags_propagate(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify that bypass flags propagate to core runs and display skipped indicators."""
    with patch(
        "manuscript_reference_lister.cli.run", return_value=({}, {})
    ) as mock_run:
        result = runner.invoke(
            cli,
            [
                "main",
                "-f",
                "doc.docx",
                "--skip-journal-update",
                "--skip-work-update",
            ],
            obj={"config": test_config},
        )

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            api="OpenAlex",
            input_file_path="doc.docx",
            input_text="",
            output_filepath=None,
            config=test_config,
            style="apa",
            journal_title=None,
            progress_callback=ANY,
            skip_journal_update=True,
            skip_work_update=True,
        )
        assert "ℹ️  Pipeline Skips:" in result.output
        assert "- Journal metadata update was skipped." in result.output
        assert "- Work DOI search and update was skipped." in result.output


def test_cli_displays_journal_anomalies_warning_table(
    runner: CliRunner, test_config: AppConfig
) -> None:
    """Verify metadata anomalies are detected and displayed inside status grids."""
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
    mock_export.sample_ok = None
    mock_export.sample_missing = None
    mock_export.samples_duplicate = []

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


def test_cli_final_summary_display_integrity(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
    tmp_path: Path,
) -> None:
    """Verify formatting metrics and output textwrapping grids on summary cards."""
    mock_manuscript = tmp_path / "mock_manuscript.docx"
    mock_manuscript.write_text("dummy content", encoding="utf-8")

    mock_export_metadata = ExportResult(
        total_rows=4,
        output_filepath=Path("/mock/path/manuscript_references.csv"),
        export_format="CSV",
        style="apa",
        ok_count=1,
        missing_count=1,
        duplicate_count=2,
        sample_ok={
            "Citation": "Smith, 2021",
            "Status": "OK",
            "Reference": "Smith, J. (2021). Short Reference Style.",
        },
        sample_missing={
            "Citation": "Alpha, 2019",
            "Status": "Warning: No doi or reference found for the citation",
            "Reference": None,
        },
        samples_duplicate=[
            {
                "Citation": "Lenard et al., 2020",
                "Status": "Warning: select the right reference",
                "Reference": "Lenard, S. J. P., Lavé, J., France-Lanord, C. (2020). "
                "Steady erosion rates in the Himalayas through late Cenozoic climatic"
                " changes. Nature Geoscience.",
            },
            {
                "Citation": "Lenard et al., 2020",
                "Status": "Warning: select the right reference",
                "Reference": "Lenard Duplicate Version B Text.",
            },
        ],
    )

    with (
        patch("manuscript_reference_lister.utils.get_config", return_value=test_config),
        patch("manuscript_reference_lister.cli.run") as mock_run,
    ):
        mock_run.return_value = ({}, mock_export_metadata)

        result = runner.invoke(
            cli,
            ["main", "-f", str(mock_manuscript)],
            obj={"config": test_config},
        )

    # Global execution
    assert result.exit_code == 0, (
        f"CLI crashed with: {result.exception}\nOutput: {result.output}"
    )

    assert "Success: Generated and saved bibliography (apa) with" in result.output
    assert "Export Summary:" in result.output
    assert "Valid references (OK)   : 1" in result.output
    assert "Missing DOI/Reference   : 1" in result.output
    assert "Ambiguous matches       : 2" in result.output

    assert "CSV Preview:" in result.output
    assert "Citation" in result.output
    assert "Status" in result.output
    assert "Reference Preview" in result.output

    assert "Warning: Missing metadata" in result.output
    assert "Warning: Multiple matches" in result.output

    # Wrapping
    assert (
        "Lenard, S. J. P., Lavé, J., France-Lanord, C. (2020). Steady" in result.output
    )

    # Alignment
    expected_padding = " " * 25 + " | " + " " * 32 + " | "
    assert expected_padding in result.output

    # Advice for user
    assert "Next Steps & Recommendations:" in result.output
    assert "search for their DOIs" in result.output
    assert "https://search.crossref.org" in result.output
    assert "delete" in result.output


def test_cli_clear_cache_option_absent_does_not_touch_files(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify cache directories remain untouched unless clear-cache flags declared."""
    with patch("manuscript_reference_lister.cli.run", return_value=({}, {})):
        result = runner.invoke(
            cli, ["main", "-f", "manuscript.docx"], obj={"config": test_config}
        )

    assert result.exit_code == 0
    assert test_local_repo_filepath.exists()
    assert "bak_" not in result.output


def test_cli_clear_cache_cancelled_by_user(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify cache cleanup stops on explicit user cancellation inputs."""
    result = runner.invoke(
        cli, ["main", "--clear-cache"], input="n\n", obj={"config": test_config}
    )

    assert result.exit_code == 0
    assert "Operation cancelled. Cache left untouched." in result.output
    assert test_local_repo_filepath.exists()


def test_cli_clear_cache_maintenance_only_success(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify standalone cache maintenance wipes cache files and generates back-ups."""
    with patch("manuscript_reference_lister.cli.run", return_value=({}, {})):
        result = runner.invoke(
            cli, ["main", "--clear-cache"], input="y\n", obj={"config": test_config}
        )

    assert result.exit_code == 0
    assert "Local cache cleared" in result.output
    assert "Done." in result.output

    assert not test_local_repo_filepath.exists()
    backups = list(test_local_repo_filepath.parent.glob("*.bak_*"))
    assert len(backups) == 1


def test_cli_clear_cache_then_proceeds_to_run(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify clean cache setup triggers first before compiling manuscript target."""
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

    assert not test_local_repo_filepath.exists()
    assert len(list(test_local_repo_filepath.parent.glob("*.bak_*"))) == 1
    mock_run.assert_called_once()


def test_cli_clear_cache_summary_displayed_at_the_very_end(
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify that cache maintenance completions print confirmation statuses."""
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
    runner: CliRunner,
    test_config: AppConfig,
    test_local_repo_filepath: Path,
) -> None:
    """Verify warning visibility if targeted database cache file is already absent."""
    test_local_repo_filepath.unlink()

    with patch("manuscript_reference_lister.cli.run", return_value=({}, {})):
        result = runner.invoke(
            cli, ["main", "--clear-cache"], input="y\n", obj={"config": test_config}
        )

    assert result.exit_code == 0
    assert (
        f"Warning: Expected cache database '{test_local_repo_filepath.name}'"
        f" was not found. Skipping."
    ) in result.output
    assert "No active cache database was found to clear." in result.output
