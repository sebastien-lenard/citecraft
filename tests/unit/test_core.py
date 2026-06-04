# tests/unit/test_core.py
import logging
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from citecraft.core import (
    AnomalousJournal,
    ExportStep,
    PipelineContext,
    PipelineOptions,
    ProgressStep,
    ReferenceFormattingStep,
    WorkUpdateStep,
    run,
)
from citecraft.services.bibliography_service import ExportResult
from citecraft.utils import AppConfig


@dataclass
class MockJournalRecord:
    input_title: str
    status: str
    ISSN: str | None


@pytest.fixture
def configured_core_config(test_config: AppConfig) -> AppConfig:
    """Configure isolated global test configuration specifically for core."""
    return test_config.model_copy(
        update={
            "crossref_api_journals_issn_url": (
                "https://mock-crossref/journals/{object_name}"
            ),
            "user_email": "test@example.com",
            "crossref_api_journals_url": "https://mock-crossref/journals",
            "crossref_api_styles_url": "https://mock-crossref/styles",
            "crossref_api_works_url": "https://mock-crossref/works",
            "doi_api_url": "https://mock-doi/{object_name}",
        }
    )


@pytest.fixture
def mock_pipeline_dependencies() -> Generator[dict[str, Any], None, None]:
    """Insulate pipeline execution from real input/output and repository layers."""
    with (
        patch("citecraft.core.DataLoader") as mock_loader,
        patch("citecraft.core.StyleRepository") as mock_style_repo,
        patch("citecraft.core.JournalRepository") as mock_journal_repo,
        patch("citecraft.core.OpenAlexWorkRepository") as mock_openalex_repo,
        patch("citecraft.core.CrossrefWorkRepository") as mock_crossref_repo,
        patch("citecraft.core.ReferenceService"),
        patch("citecraft.core.BibliographyService") as mock_bib_service,
        patch("citecraft.core.get_http_client_registry"),
    ):
        mock_loader.return_value.extract_text_from_docx.return_value = "Sample text"
        mock_style_repo.return_value.favored_style_is_valid = True
        mock_bib_service.return_value.export_to_csv.return_value = ExportResult(
            total_rows=0,
            output_filepath=Path("dummy_references.csv"),
            export_format="CSV",
        )

        yield {
            "loader": mock_loader,
            "journal": mock_journal_repo,
            "work": mock_openalex_repo,
            "openalex": mock_openalex_repo,
            "crossref": mock_crossref_repo,
        }


def test_run_pipeline_progress_callback_sequences(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify that core pipeline calls progress callbacks sequentially."""
    tracked_steps: list[ProgressStep] = []

    def sample_callback(step: ProgressStep) -> None:
        tracked_steps.append(step)

    run(
        PipelineOptions(
            input_file_path="dummy.docx",
            input_text=None,
            config=configured_core_config,
            progress_callback=sample_callback,
        )
    )

    # 5 steps, each having a 'started' and 'completed' trigger
    assert len(tracked_steps) == 10

    assert tracked_steps[0].step_name == "parsing"
    assert tracked_steps[0].status == "started"
    assert tracked_steps[0].current == 0
    assert tracked_steps[0].total == 5

    assert tracked_steps[1].step_name == "parsing"
    assert tracked_steps[1].status == "completed"
    assert tracked_steps[1].current == 1
    assert tracked_steps[1].total == 5


def test_run_pipeline_with_journal_title_style_lookup(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify that specifying a journal title triggers style lookup."""
    with patch("citecraft.core.StyleRepository") as mock_style_repo:
        mock_style_inst = mock_style_repo.return_value
        mock_style_inst.favored_style_is_valid = True
        mock_style_inst.favored_style = "copernicus-publications"
        mock_style_inst.csl_content = "<style>XML</style>"

        run(
            PipelineOptions(
                input_file_path="dummy.docx",
                input_text=None,
                journal_title="Geomorphology",
                config=configured_core_config,
            )
        )

        mock_style_repo.assert_called_once_with(
            favored_style="apa",
            favored_journal_title="Geomorphology",
            config=configured_core_config,
        )
        mock_style_inst.fetch_style_metadata.assert_called_once()
        mock_style_inst.validate_favored_style.assert_called_once()


@pytest.mark.parametrize(
    "skip_journal, skip_work, expect_journal_update, expect_work_update, expected_logs",
    [
        # Case A: Both pipeline sync scopes are explicitly bypassed
        (
            True,
            True,
            False,
            False,
            [
                "Skipped updating journal metadata via flag.",
                "Skipped finding and linking work DOI to citations via flag.",
            ],
        ),
        # Case B: Journal sync is executed, work sync is bypassed
        (
            False,
            True,
            True,
            False,
            ["Skipped finding and linking work DOI to citations via flag."],
        ),
        # Case C: Journal sync is bypassed, work sync is executed
        (
            True,
            False,
            False,
            True,
            ["Skipped updating journal metadata via flag."],
        ),
        # Case D: Full end-to-end sync executed without any bypass steps
        (
            False,
            False,
            True,
            True,
            [],
        ),
    ],
)
def test_run_pipeline_bypass_controls(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    skip_journal: bool,
    skip_work: bool,
    expect_journal_update: bool,
    expect_work_update: bool,
    expected_logs: list[str],
) -> None:
    """Verify bypass flags prevent specific repository updates."""
    mock_journal_inst = mock_pipeline_dependencies["journal"].return_value
    mock_work_inst = mock_pipeline_dependencies["work"].return_value

    with caplog.at_level(logging.INFO):
        run(
            PipelineOptions(
                input_file_path="dummy.docx",
                input_text=None,
                config=configured_core_config,
                skip_journal_update=skip_journal,
                skip_work_update=skip_work,
            )
        )

    # Verify update trigger parameters
    if expect_journal_update:
        mock_journal_inst.update_all.assert_called_once()
    else:
        mock_journal_inst.update_all.assert_not_called()

    if expect_work_update:
        mock_work_inst.update_all.assert_called_once()
    else:
        mock_work_inst.update_all.assert_not_called()

    # Verify appropriate bypass logs are captured
    for expected_log in expected_logs:
        assert expected_log in caplog.text


def test_run_pipeline_no_input_raises_value_error(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify pipeline termination when both file and text are missing."""
    with pytest.raises(ValueError, match="No manuscript text or input file provided"):
        run(
            PipelineOptions(
                input_file_path=None,
                input_text=None,
                config=configured_core_config,
            )
        )


def test_run_pipeline_invalid_style_raises_value_error(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify error raised when specified CSL style is not found in registry."""
    with patch("citecraft.core.StyleRepository") as mock_style_repo:
        mock_style_repo.return_value.favored_style_is_valid = False
        mock_style_repo.return_value.favored_style = "unsupported-style"

        with pytest.raises(ValueError, match="is not found in CSL repository"):
            run(
                PipelineOptions(
                    input_file_path="dummy.docx",
                    style="unsupported-style",
                    config=configured_core_config,
                )
            )


def test_reference_formatting_step_invalid_style_raises_error(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify step raises ValueError if evaluated with an invalid style state."""
    ctx = PipelineContext(config=configured_core_config)
    with patch("citecraft.core.StyleRepository") as mock_style_repo:
        mock_style_inst = mock_style_repo.return_value
        mock_style_inst.favored_style_is_valid = False
        mock_style_inst.favored_style = "broken-style"
        ctx.style_repo = mock_style_inst

        step = ReferenceFormattingStep()
        with pytest.raises(ValueError, match="Unvalidated style 'broken-style'"):
            step.execute(ctx)


def test_export_step_extracts_anomalous_journals(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify export step extracts and compiles journals with non-OK status."""
    ctx = PipelineContext(config=configured_core_config)
    ctx.output_filepath = Path("dummy_output.csv")

    mock_journal_inst = mock_pipeline_dependencies["journal"].return_value
    mock_journal_inst.records = [
        MockJournalRecord(
            input_title="Errant Journal", status="NOT_FOUND", ISSN="1234-5678"
        )
    ]
    mock_journal_inst.get_issns_by_input_title.return_value = ["1234-5678"]

    step = ExportStep()
    step.execute(ctx)

    assert len(ctx.anomalous_journals) == 1
    anomaly: AnomalousJournal = ctx.anomalous_journals[0]
    assert anomaly.input_title == "Errant Journal"
    assert anomaly.status == "NOT_FOUND"
    assert anomaly.issn == "1234-5678"
    assert anomaly.issns_found == "1234-5678"


def test_export_step_resolves_default_filepath(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify that export step uses a default filepath if none is specified."""
    ctx = PipelineContext(config=configured_core_config, output_filepath=None)
    step = ExportStep()
    step.execute(ctx)

    expected_path = configured_core_config.output_dir_path / "manuscript_references.csv"
    assert ctx.output_filepath == expected_path


def test_run_pipeline_with_crossref_api(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Verify selection of CrossrefWorkRepository when crossref API is specified."""
    run(
        PipelineOptions(
            input_file_path="dummy.docx",
            api="Crossref",
            config=configured_core_config,
        )
    )
    mock_pipeline_dependencies["crossref"].assert_called_once()


def test_logging_contains_structured_extras(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that execution steps write logs containing structured extra details."""
    with caplog.at_level(logging.INFO):
        run(
            PipelineOptions(
                input_file_path="dummy.docx",
                config=configured_core_config,
            )
        )

    parsing_logs = [
        record
        for record in caplog.records
        if getattr(record, "step", None) == "parsing"
    ]
    assert len(parsing_logs) > 0
    assert hasattr(parsing_logs[0], "step")


def test_work_update_step_initializes_journal_repo_if_none(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Cover L209 in WorkUpdateStep: initialization of journal_repo if None."""
    ctx = PipelineContext(config=configured_core_config)
    assert ctx.journal_repo is None

    step = WorkUpdateStep()
    step.execute(ctx)

    assert ctx.journal_repo is not None
    mock_pipeline_dependencies["journal"].assert_called_once()


def test_reference_formatting_step_initializes_defaults_if_none(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Cover L266 (case _) and L270 (style_repo is None) in ReferenceFormattingStep."""
    ctx = PipelineContext(config=configured_core_config, api="UnsupportedAPI")
    assert ctx.work_repo is None
    assert ctx.style_repo is None
    assert ctx.journal_repo is None

    with patch("citecraft.core.StyleRepository") as mock_style_repo:
        mock_style_inst = mock_style_repo.return_value
        mock_style_inst.favored_style_is_valid = True
        mock_style_inst.csl_content = "<style></style>"
        mock_style_inst.favored_style = "apa"

        step = ReferenceFormattingStep()
        step.execute(ctx)

    assert ctx.journal_repo is not None
    assert ctx.work_repo is not None
    assert ctx.style_repo is not None
    mock_pipeline_dependencies["crossref"].assert_called_once()


def test_export_step_with_missing_style_repo_uses_default_style(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Cover style evaluation when ctx.style_repo is None in ExportStep."""
    ctx = PipelineContext(
        config=configured_core_config,
        style="vancouver",
        output_filepath=Path("dummy_out.csv"),
    )
    assert ctx.style_repo is None

    step = ExportStep()
    step.execute(ctx)

    assert ctx.export_result is not None
    assert ctx.export_result.style == "vancouver"


def test_export_step_initializes_crossref_work_repo_if_none(
    configured_core_config: AppConfig,
    mock_pipeline_dependencies: dict[str, Any],
) -> None:
    """Cover fallback case _ to CrossrefWorkRepository when work_repo is None."""
    ctx = PipelineContext(
        config=configured_core_config,
        api="UnsupportedAPI",
        output_filepath=Path("dummy_out.csv"),
    )
    assert ctx.work_repo is None

    step = ExportStep()
    step.execute(ctx)

    assert ctx.work_repo is not None
    mock_pipeline_dependencies["crossref"].assert_called_once()
