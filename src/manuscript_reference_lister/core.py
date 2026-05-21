from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from .network import get_http_client_registry
from .parsers import CitationParser, JournalParser
from .repositories import (
    DoiRepository,
    JournalRepository,
    StyleRepository,
    WorkRepository,
)
from .services import BibliographyService, ReferenceService
from .utils import DataLoader
from .utils.config import AppConfig, get_config


class ProgressStep(NamedTuple):
    step_name: str  # Ex: "journals_update", "works_update", "bibliography_service"
    current: int  # Count of processed elements
    total: int  # Total count of elements
    message: str  # Optional UI message
    status: str = "started"


def run(
    input_file_path: str | None,
    input_text: str | None,
    style: str = "apa",
    output_filepath: str | Path | None = None,
    config: AppConfig | None = None,
    progress_callback: Callable[[ProgressStep], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Orchestration of the manuscript-reference-lister pipeline.
    Returns a tuple: (anomalies_map, export_metadata), with map of problematic journals
    and bibliography export information."""
    total_steps = 4
    if progress_callback:
        progress_callback(
            ProgressStep(
                "parsing",
                0,
                total_steps,
                "Parsing manuscript and checking style...",
                status="started",
            )
        )
    config = config or get_config()
    if not input_text:
        input_text = DataLoader(input_file_path).extract_text_from_docx()
    style_repo = StyleRepository(style, config=config)
    style_repo.validate_favored_style()
    if style_repo.favored_style_is_valid is False:
        raise ValueError(f"Style {style} is not found in crossref api styles.")

    journal_parser = JournalParser()
    journal_required_titles = journal_parser.extract_all(input_text)
    citation_parser = CitationParser(config=config)
    citations = citation_parser.extract_all(input_text)

    if progress_callback:
        progress_callback(
            ProgressStep(
                "parsing",
                1,
                total_steps,
                "Manuscript parsed and style checked",
                status="completed",
            )
        )

    if progress_callback:
        progress_callback(
            ProgressStep(
                "journals",
                1,
                total_steps,
                "Updating journal metadata...",
                status="started",
            )
        )
    journal_repo = JournalRepository(config=config)
    journal_repo.load_all()
    journal_repo.deduplicate()
    journal_repo.merge_new_titles(journal_required_titles)
    journal_repo.update_all()
    journal_repo.save_all()
    if progress_callback:
        progress_callback(
            ProgressStep(
                "journals",
                2,
                total_steps,
                "Journal metadata updated",
                status="completed",
            )
        )

    if progress_callback:
        progress_callback(
            ProgressStep(
                "works",
                2,
                total_steps,
                "Finding and linking work DOI to citations...",
                status="started",
            )
        )
    work_repo = WorkRepository(config=config)
    work_repo.load_all()
    work_repo.merge_new_works(citations)
    ISSNs = list({j.ISSN for j in journal_repo.records if j.ISSN is not None})
    work_repo.update_all(ISSNs=ISSNs)
    if progress_callback:
        progress_callback(
            ProgressStep(
                "works",
                3,
                total_steps,
                "Work DOI found and linked to citations...",
                status="completed",
            )
        )

    if progress_callback:
        progress_callback(
            ProgressStep(
                "references", 3, total_steps, "Formatting bibliographic references..."
            )
        )
    doi_repo = DoiRepository(config=config)

    ReferenceService.fill_missing_references(
        records=work_repo.records,
        doi_repo=doi_repo,
        target_style=style_repo.favored_style,
    )

    work_repo.save_all()
    if progress_callback:
        progress_callback(
            ProgressStep(
                "references",
                4,
                total_steps,
                "Bibliographic references found and saved",
                status="completed",
            )
        )

    if not output_filepath:
        config.ensure_output_directory()
        output_filepath = work_repo.config.output_dir_path / "manuscript_references.csv"
    else:
        output_filepath = Path(output_filepath)
        output_filepath.parent.mkdir(parents=True, exist_ok=True)

    export_result = BibliographyService.export_to_csv(
        citations=citations, works=work_repo.records, output_path=output_filepath
    )

    get_http_client_registry().close_all()
    get_http_client_registry.cache_clear()

    anomalies_map = {}
    for j in journal_repo.records:
        if j.status != "OK":
            all_found_issns = journal_repo.get_issns_by_input_title(j.input_title)

            anomalies_map[j.identity_key] = {
                "input_title": j.input_title,
                "status": j.status,
                "issn": j.ISSN or "",
                "issns_found": ", ".join(all_found_issns) if all_found_issns else "",
            }

    return anomalies_map, export_result
