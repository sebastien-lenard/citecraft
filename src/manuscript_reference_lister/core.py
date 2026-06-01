import logging
from collections.abc import Callable
from dataclasses import is_dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict

from manuscript_reference_lister.schemas import CitationMetadata

from .network import get_http_client_registry
from .parsers import CitationParser, JournalParser
from .repositories import (
    CrossrefWorkRepository,
    DoiRepository,
    JournalRepository,
    OpenAlexWorkRepository,
    StyleRepository,
    WorkRepository,
)
from .services import BibliographyService, ExportResult, ReferenceService
from .utils import DataLoader
from .utils.config import AppConfig, get_config

logger = logging.getLogger(__name__)


class ProgressStep(NamedTuple):
    step_name: str  # Ex: "parsing", "journals", "works", "references"
    current: int  # Count of processed elements
    total: int  # Total count of elements
    message: str  # Optional UI message
    status: str = "started"


class PipelineContext(BaseModel):
    """State container shared along the execution of the pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input parameters
    api: str = "OpenAlex"
    input_file_path: str | None = None
    input_text: str | None = None
    style: str = "apa"
    journal_title: str | None = None
    output_filepath: Path | None = None
    config: AppConfig
    skip_journal_update: bool = False
    skip_work_update: bool = False

    # Intermediate state data
    citations: list[CitationMetadata] = []
    journal_required_titles: list[str] = []

    # Repositories and services
    style_repo: StyleRepository | None = None
    journal_repo: JournalRepository | None = None
    work_repo: WorkRepository | None = None
    doi_repo: DoiRepository | None = None

    # Output payloads
    anomalies_map: dict[str, Any] = {}
    export_result: ExportResult | None = None


class PipelineStep(Protocol):
    """Structural contract to define a pipeline step (PEP 544 Protocol)."""

    @property
    def name(self) -> str: ...

    @property
    def message(self) -> str: ...

    def execute(self, ctx: PipelineContext) -> None:
        """Run standard step logic and update state context."""
        ...


# =============================================================================
# PIPELINE STEPS
# =============================================================================


class ParsingStep:
    name: str = "parsing"
    message: str = "Parsing manuscript and checking style..."

    def execute(self, ctx: PipelineContext) -> None:
        if not ctx.input_text and ctx.input_file_path:
            ctx.input_text = DataLoader(ctx.input_file_path).extract_text_from_docx()
        if not ctx.input_text:
            raise ValueError("No manuscript text or input file provided.")

        ctx.style_repo = StyleRepository(
            favored_style=ctx.style,
            favored_journal_title=ctx.journal_title,
            config=ctx.config,
        )
        ctx.style_repo.fetch_style_metadata()
        ctx.style_repo.validate_favored_style()

        if not ctx.style_repo.favored_style_is_valid:
            style_identifier = (
                ctx.style_repo.favored_style or ctx.journal_title or ctx.style
            )
            raise ValueError(
                f"Style '{style_identifier}' is not found in CSL repository "
                "https://github.com/citation-style-language/styles."
            )

        ctx.journal_required_titles = JournalParser().extract_all(ctx.input_text)
        ctx.citations = CitationParser(config=ctx.config).extract_all(ctx.input_text)


class JournalUpdateStep:
    name: str = "journals"
    message: str = "Updating journal metadata..."

    def execute(self, ctx: PipelineContext) -> None:
        ctx.journal_repo = JournalRepository(config=ctx.config)
        ctx.journal_repo.load_all()
        ctx.journal_repo.deduplicate()
        ctx.journal_repo.merge_new_titles(ctx.journal_required_titles)
        if not ctx.skip_journal_update:
            ctx.journal_repo.update_all()
        else:
            logger.info("Skipped updating journal metadata.")
        ctx.journal_repo.save_all()


class WorkUpdateStep:
    name: str = "works"
    message: str = "Finding and linking work DOI to citations..."

    def execute(self, ctx: PipelineContext) -> None:
        if ctx.journal_repo is None:
            ctx.journal_repo = JournalRepository(config=ctx.config)
            ctx.journal_repo.load_all()

        match ctx.api:
            case "OpenAlex":
                ctx.work_repo = OpenAlexWorkRepository(config=ctx.config)
            case _:
                ctx.work_repo = CrossrefWorkRepository(config=ctx.config)

        ctx.work_repo.load_all()
        ctx.work_repo.merge_new_works(ctx.citations)

        if not ctx.skip_work_update:
            issns = ctx.journal_repo.get_unique_issns_for_titles(
                ctx.journal_required_titles
            )
            ctx.work_repo.update_all(ISSNs=issns)
        else:
            logger.info("Skipped finding and linking work DOI to citations.")


class ReferenceFormattingStep:
    name: str = "references"
    message: str = "Formatting bibliographic references..."

    def execute(self, ctx: PipelineContext) -> None:
        if ctx.journal_repo is None:
            ctx.journal_repo = JournalRepository(config=ctx.config)
            ctx.journal_repo.load_all()

        if ctx.work_repo is None:
            match ctx.api:
                case "OpenAlex":
                    ctx.work_repo = OpenAlexWorkRepository(config=ctx.config)
                case _:
                    ctx.work_repo = CrossrefWorkRepository(config=ctx.config)
            ctx.work_repo.load_all()

        if ctx.style_repo is None:
            ctx.style_repo = StyleRepository(
                favored_style=ctx.style,
                favored_journal_title=ctx.journal_title,
                config=ctx.config,
            )

        ctx.doi_repo = DoiRepository(config=ctx.config)
        reference_service = ReferenceService(config=ctx.config)

        reference_service.fill_missing_references(
            records=ctx.work_repo.records,
            doi_repo=ctx.doi_repo,
            csl_style_content=ctx.style_repo.csl_content,
            target_style=ctx.style_repo.favored_style,
        )
        ctx.work_repo.save_all()


class ExportStep:
    name: str = "export"
    message: str = "Exporting bibliography to CSV..."

    def execute(self, ctx: PipelineContext) -> None:
        if ctx.work_repo is None:
            match ctx.api:
                case "OpenAlex":
                    ctx.work_repo = OpenAlexWorkRepository(config=ctx.config)
                case _:
                    ctx.work_repo = CrossrefWorkRepository(config=ctx.config)
            ctx.work_repo.load_all()

        if ctx.journal_repo is None:
            ctx.journal_repo = JournalRepository(config=ctx.config)
            ctx.journal_repo.load_all()

        if not ctx.output_filepath:
            ctx.config.ensure_output_directory()
            ctx.output_filepath = (
                ctx.config.output_dir_path / "manuscript_references.csv"
            )
        else:
            ctx.output_filepath.parent.mkdir(parents=True, exist_ok=True)

        bibliography_service = BibliographyService(config=ctx.config)
        ctx.export_result = bibliography_service.export_to_csv(
            citations=ctx.citations,
            works=ctx.work_repo.records,
            output_path=ctx.output_filepath,
        )

        if ctx.export_result is not None and is_dataclass(ctx.export_result):
            style_name = ctx.style_repo.favored_style if ctx.style_repo else ctx.style
            ctx.export_result = replace(ctx.export_result, style=style_name)

        for j in ctx.journal_repo.records:
            if j.status != "OK":
                all_found_issns = ctx.journal_repo.get_issns_by_input_title(
                    j.input_title
                )
                ctx.anomalies_map[j.identity_key] = {
                    "input_title": j.input_title,
                    "status": j.status,
                    "issn": j.ISSN or "",
                    "issns_found": ", ".join(all_found_issns)
                    if all_found_issns
                    else "",
                }


# =============================================================================
# PIPELINE FUNCTION
# =============================================================================
def run(
    input_file_path: str | None,
    input_text: str | None,
    *,
    api: str = "OpenAlex",
    style: str = "apa",
    journal_title: str | None = None,
    output_filepath: str | Path | None = None,
    config: AppConfig | None = None,
    progress_callback: Callable[[ProgressStep], None] | None = None,
    skip_journal_update: bool = False,
    skip_work_update: bool = False,
) -> tuple[dict[str, Any], ExportResult | dict[str, Any]]:
    """Orchestrate the linear citation processing pipeline step-by-step.
    Returns a tuple: (anomalies_map, export_metadata), with map of problematic journals
    and bibliography export information."""
    app_config = config or get_config()
    out_path = Path(output_filepath) if output_filepath else None

    ctx = PipelineContext(
        api=api,
        input_file_path=input_file_path,
        input_text=input_text,
        style=style,
        journal_title=journal_title,
        output_filepath=out_path,
        config=app_config,
        skip_journal_update=skip_journal_update,
        skip_work_update=skip_work_update,
    )

    steps: list[PipelineStep] = [
        ParsingStep(),
        JournalUpdateStep(),
        WorkUpdateStep(),
        ReferenceFormattingStep(),
        ExportStep(),
    ]

    total_steps = len(steps)

    try:
        for idx, step in enumerate(steps):
            if progress_callback:
                progress_callback(
                    ProgressStep(
                        step_name=step.name,
                        current=idx,
                        total=total_steps,
                        message=step.message,
                        status="started",
                    )
                )

            step.execute(ctx)

            if progress_callback:
                progress_callback(
                    ProgressStep(
                        step_name=step.name,
                        current=idx + 1,
                        total=total_steps,
                        message=f"Finished: {step.message}",
                        status="completed",
                    )
                )
    finally:
        get_http_client_registry().close_all()
        get_http_client_registry.cache_clear()

    return ctx.anomalies_map, ctx.export_result
