from pathlib import Path

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


def run(
    input_file_path: str | None,
    input_text: str | None,
    style: str = "apa",
    output_filepath: str | Path | None = None,
    config: AppConfig | None = None,
) -> dict[str, str]:
    """Orchestration of the manuscript-reference-lister pipeline.
    Returns a dictionary of problematic journals mapped to their error status."""

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

    journal_repo = JournalRepository(config=config)
    journal_repo.load_all()
    journal_repo.deduplicate()
    journal_repo.merge_new_titles(journal_required_titles)
    journal_repo.update_all()
    journal_repo.save_all()

    work_repo = WorkRepository(config=config)
    work_repo.load_all()
    work_repo.merge_new_works(citations)
    ISSNs = list({j.ISSN for j in journal_repo.records if j.ISSN is not None})
    work_repo.update_all(ISSNs=ISSNs)

    doi_repo = DoiRepository(config=config)
    ReferenceService.fill_missing_references(
        records=work_repo.records,
        doi_repo=doi_repo,
        target_style=style_repo.favored_style,
    )
    work_repo.save_all()

    if not output_filepath:
        config.ensure_output_directory()
        output_filepath = work_repo.config.output_dir_path / "manuscript_references.csv"
    else:
        output_filepath = Path(output_filepath)
        output_filepath.parent.mkdir(parents=True, exist_ok=True)

    BibliographyService.export_to_csv(
        citations=citations, works=work_repo.records, output_path=output_filepath
    )

    get_http_client_registry().close_all()
    get_http_client_registry.cache_clear()

    anomalies_map = {}
    for j in journal_repo.records:
        if j.status != "OK":
            anomalies_map[j.input_title] = j.status
    return anomalies_map
