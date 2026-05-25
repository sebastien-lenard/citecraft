from pathlib import Path
from unittest.mock import patch

import pytest

from manuscript_reference_lister.core import ProgressStep, run
from manuscript_reference_lister.utils import AppConfig


@pytest.fixture
def mock_config(tmp_path: Path) -> AppConfig:
    """Insulated testing config instance, with explicit configuration of obligatory
    attributes and bypass of .env.
    """
    config = AppConfig(
        _settings_vars={},  # Empty context dictionary to bypass .env
        crossref_api_journals_issn_url="http://mock-crossref/journals/{issn}",
        crossref_api_email="test@example.com",
        crossref_api_journals_url="http://mock-crossref/journals",
        crossref_api_styles_url="http://mock-crossref/styles",
        crossref_api_works_url="http://mock-crossref/works",
        doi_api_url="http://mock-doi/{doi}",
        local_repo_dir_path=tmp_path / "repo",
        output_dir_path=tmp_path / "output",
    )
    return config


@pytest.fixture
def mock_pipeline_dependencies():
    """Insulates pipeline from real input/output and complex methods (inc. API calls)."""
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
    mock_config: AppConfig, mock_pipeline_dependencies
) -> None:
    """Check that the pipeline notifies callback at each start/end of step with correct
    indices.
    """
    tracked_steps = []

    def sample_callback(step: ProgressStep) -> None:
        tracked_steps.append(step)

    # Full execution
    run(
        input_file_path="dummy.docx",
        input_text=None,
        config=mock_config,
        progress_callback=sample_callback,
    )

    # 5 (steps) x 2 (states) notifications
    assert len(tracked_steps) == 10

    assert tracked_steps[0].step_name == "parsing"
    assert tracked_steps[0].status == "started"
    assert tracked_steps[0].current == 0
    assert tracked_steps[0].total == 5

    assert tracked_steps[1].step_name == "parsing"
    assert tracked_steps[1].status == "completed"
    assert tracked_steps[1].current == 1
    assert tracked_steps[1].total == 5


def test_run_pipeline_skips_logs_and_calls(
    mock_config: AppConfig, mock_pipeline_dependencies, caplog: pytest.LogCaptureFixture
) -> None:
    """Check that skip flags prevent updates and generate logs"""
    import logging

    mock_journal_inst = mock_pipeline_dependencies["journal"].return_value
    mock_work_inst = mock_pipeline_dependencies["work"].return_value

    with caplog.at_level(logging.INFO):
        run(
            input_file_path="dummy.docx",
            input_text=None,
            config=mock_config,
            skip_journal_update=True,
            skip_work_update=True,
        )

    mock_journal_inst.load_all.assert_called_once()
    mock_journal_inst.save_all.assert_called_once()
    mock_journal_inst.update_all.assert_not_called()

    mock_work_inst.load_all.assert_called_once()
    mock_work_inst.update_all.assert_not_called()

    assert "Skipped updating journal metadata." in caplog.text
    assert "Skipped finding and linking work DOI to citations." in caplog.text
