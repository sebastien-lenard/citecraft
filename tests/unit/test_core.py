import logging
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from manuscript_reference_lister.core import ProgressStep, run
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def configured_core_config(test_config: AppConfig) -> AppConfig:
    """Configure the isolated global test configuration specifically for core execution
    boundaries."""
    test_config.crossref_api_journals_issn_url = "https://mock-crossref/journals/{issn}"
    test_config.crossref_api_email = "test@example.com"
    test_config.crossref_api_journals_url = "https://mock-crossref/journals"
    test_config.crossref_api_styles_url = "https://mock-crossref/styles"
    test_config.crossref_api_works_url = "https://mock-crossref/works"
    test_config.doi_api_url = "https://mock-doi/{doi}"
    return test_config


@pytest.fixture
def mock_pipeline_dependencies() -> Generator[dict[str, Any], None, None]:
    """Insulate pipeline execution from real input/output, repository layers, and API
    clients."""
    with (
        patch("manuscript_reference_lister.core.DataLoader") as mock_loader,
        patch("manuscript_reference_lister.core.StyleRepository") as mock_style_repo,
        patch(
            "manuscript_reference_lister.core.JournalRepository"
        ) as mock_journal_repo,
        patch("manuscript_reference_lister.core.WorkRepository") as mock_work_repo,
        patch("manuscript_reference_lister.core.ReferenceService"),
        patch("manuscript_reference_lister.core.BibliographyService"),
        patch("manuscript_reference_lister.core.get_http_client_registry"),
    ):
        mock_loader.return_value.extract_text_from_docx.return_value = "Sample text"
        mock_style_repo.return_value.favored_style_is_valid = True

        yield {
            "loader": mock_loader,
            "journal": mock_journal_repo,
            "work": mock_work_repo,
        }


def test_run_pipeline_progress_callback_sequences(
    configured_core_config: AppConfig, mock_pipeline_dependencies: dict[str, Any]
) -> None:
    """Verify that the core pipeline calls progress callbacks sequentially with accurate
    index states."""
    tracked_steps: list[ProgressStep] = []

    def sample_callback(step: ProgressStep) -> None:
        tracked_steps.append(step)

    run(
        input_file_path="dummy.docx",
        input_text=None,
        config=configured_core_config,
        progress_callback=sample_callback,
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
                "Skipped updating journal metadata.",
                "Skipped finding and linking work DOI to citations.",
            ],
        ),
        # Case B: Journal sync is executed, work sync is bypassed
        (
            False,
            True,
            True,
            False,
            ["Skipped finding and linking work DOI to citations."],
        ),
        # Case C: Journal sync is bypassed, work sync is executed
        (
            True,
            False,
            False,
            True,
            ["Skipped updating journal metadata."],
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
    """Verify bypass flags prevent specific repository updates and log warning
    descriptions."""
    mock_journal_inst = mock_pipeline_dependencies["journal"].return_value
    mock_work_inst = mock_pipeline_dependencies["work"].return_value

    with caplog.at_level(logging.INFO):
        run(
            input_file_path="dummy.docx",
            input_text=None,
            config=configured_core_config,
            skip_journal_update=skip_journal,
            skip_work_update=skip_work,
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
