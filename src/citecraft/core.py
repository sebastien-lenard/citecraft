# src/citecraft/core.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Core execution pipeline engine and context orchestration for CiteCraft."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, is_dataclass, replace
from pathlib import Path
from typing import NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict, Field

from citecraft.schemas import CitationMetadata

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


@dataclass(frozen=True)
class AnomalousJournal:
    """Data carrier representing journals with no ISSN or incomplete metadata."""

    input_title: str
    status: str
    issn: str
    issns_found: str


class ProgressStep(NamedTuple):
    """Immutable data record representing the progress of a pipeline step."""

    step_name: str  # Ex: "parsing", "journals", "works", "references"
    current: int  # Count of processed elements
    total: int  # Total count of elements
    message: str  # Optional UI message
    status: str = "started"


class PipelineOptions(BaseModel):
    """Encapsulated execution parameters for the linear pipeline run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    input_file_path: str | Path | None = None
    input_text: str | None = None
    api: str = "OpenAlex"
    style: str = "apa"
    journal_title: str | None = None
    output_filepath: str | Path | None = None
    config: AppConfig | None = None
    progress_callback: Callable[[ProgressStep], None] | None = None
    skip_journal_update: bool = False
    skip_work_update: bool = False


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
    citations: list[CitationMetadata] = Field(default_factory=list)
    journal_required_titles: list[str] = Field(default_factory=list)

    # Repositories and services
    style_repo: StyleRepository | None = None
    journal_repo: JournalRepository | None = None
    work_repo: WorkRepository | None = None
    doi_repo: DoiRepository | None = None

    # Output payloads
    anomalous_journals: list[AnomalousJournal] = Field(default_factory=list)
    export_result: ExportResult | None = None


class PipelineStep(Protocol):
    """Structural contract to define a pipeline step (PEP 544 Protocol)."""

    @property
    def name(self) -> str:
        """The unique identifier string for the pipeline step execution."""
        ...

    @property
    def message(self) -> str:
        """The user-facing message string describing the active step."""
        ...

    def execute(self, ctx: PipelineContext) -> None:
        """Run standard step logic and update state context."""
        ...


# =============================================================================
# PIPELINE STEPS
# =============================================================================


class ParsingStep:
    """Pipeline step responsible for extracting citations and validating styles."""

    name: str = "parsing"
    message: str = "Parsing manuscript and checking style..."

    def execute(self, ctx: PipelineContext) -> None:
        """Parse manuscript texts and resolve target metadata configurations."""
        logger.info(
            "Executing ParsingStep: loading and parsing manuscript input.",
            extra={"step": self.name, "input_path": ctx.input_file_path},
        )
        if not ctx.input_text and ctx.input_file_path:
            logger.info(
                "Loading text from file: %s",
                ctx.input_file_path,
                extra={"step": self.name},
            )
            ctx.input_text = DataLoader(ctx.input_file_path).extract_text_from_docx()
        if not ctx.input_text:
            err_msg = "No manuscript text or input file provided."
            raise ValueError(err_msg)

        logger.info(
            "Resolving and validating CSL style: %s",
            ctx.style,
            extra={"step": self.name, "target_style": ctx.style},
        )
        ctx.style_repo = StyleRepository(
            favored_style=ctx.style,
            favored_journal_title=ctx.journal_title,
            config=ctx.config,
        )
        ctx.style_repo.fetch_style_metadata()
        ctx.style_repo.validate_favored_style()

        if not ctx.style_repo.favored_style_is_valid:
            style_id = ctx.style_repo.favored_style or ctx.journal_title or ctx.style
            err_msg = (
                f"Style '{style_id}' is not found in CSL repository "
                "https://github.com/citation-style-language/styles."
            )
            raise ValueError(err_msg)

        ctx.journal_required_titles = JournalParser().extract_all(ctx.input_text)
        ctx.citations = CitationParser(config=ctx.config).extract_all(ctx.input_text)
        logger.info(
            "Parsing completed structurally.",
            extra={
                "step": self.name,
                "citations_count": len(ctx.citations),
                "journals_count": len(ctx.journal_required_titles),
            },
        )


class JournalUpdateStep:
    """Pipeline step handling database sync for missing or outdated journals."""

    name: str = "journals"
    message: str = "Updating journal metadata..."

    def execute(self, ctx: PipelineContext) -> None:
        """Execute cross-referencing sequences against global journal registries."""
        logger.info(
            "Executing JournalUpdateStep: updating journal registry databases.",
            extra={
                "step": self.name,
                "required_titles_count": len(ctx.journal_required_titles),
            },
        )
        ctx.journal_repo = JournalRepository(config=ctx.config)
        ctx.journal_repo.load_all()
        ctx.journal_repo.deduplicate()
        ctx.journal_repo.merge_new_titles(ctx.journal_required_titles)
        if not ctx.skip_journal_update:
            logger.info(
                "Querying remote endpoints for outdated journal metadata.",
                extra={"step": self.name},
            )
            ctx.journal_repo.update_all()
        else:
            logger.info(
                "Skipped updating journal metadata via flag.",
                extra={"step": self.name},
            )
        ctx.journal_repo.save_all()
        logger.info(
            "Journal metadata update and saving process finalized.",
            extra={"step": self.name},
        )


class WorkUpdateStep:
    """Pipeline step that fetches, aligns, and merges metadata for target works."""

    name: str = "works"
    message: str = "Finding and linking work DOI to citations..."

    def execute(self, ctx: PipelineContext) -> None:
        """Match and update target citations using designated service providers."""
        logger.info(
            "Executing WorkUpdateStep: matching citations against target works.",
            extra={"step": self.name, "api_engine": ctx.api},
        )
        if ctx.journal_repo is None:
            ctx.journal_repo = JournalRepository(config=ctx.config)
            ctx.journal_repo.load_all()

        match ctx.api:
            case "OpenAlex":
                logger.info(
                    "Configuring work repository to use OpenAlex source.",
                    extra={"step": self.name},
                )
                ctx.work_repo = OpenAlexWorkRepository(config=ctx.config)
            case _:
                logger.info(
                    "Configuring work repository to use Crossref source.",
                    extra={"step": self.name},
                )
                ctx.work_repo = CrossrefWorkRepository(config=ctx.config)

        ctx.work_repo.load_all()
        ctx.work_repo.merge_new_works(ctx.citations)

        if not ctx.skip_work_update:
            issns = ctx.journal_repo.get_unique_issns_for_titles(
                ctx.journal_required_titles,
            )
            logger.info(
                "Updating local works database for target ISSNs.",
                extra={"step": self.name, "issns_count": len(issns) if issns else 0},
            )
            ctx.work_repo.update_all(issns=issns)
        else:
            logger.info(
                "Skipped finding and linking work DOI to citations via flag.",
                extra={"step": self.name},
            )
        logger.info(
            "Work database sync completed.",
            extra={"step": self.name, "works_count": len(ctx.work_repo.records)},
        )


class ReferenceFormattingStep:
    """Pipeline step rendering the final bibliography through CSL engines."""

    name: str = "references"
    message: str = "Formatting bibliographic references..."

    def execute(self, ctx: PipelineContext) -> None:
        """Apply style metadata transformations to produce valid references."""
        logger.info(
            "Executing ReferenceFormattingStep: formatting citation output.",
            extra={"step": self.name},
        )
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

        if not ctx.style_repo.favored_style_is_valid:
            style_id = ctx.style_repo.favored_style or ctx.journal_title or ctx.style
            err_msg = (
                f"Unvalidated style '{style_id}'. Code implementation "
                "might not run ctx.style_repo.fetch_style_metadata() and "
                "ctx.style_repo.validate_favored_style()."
            )
            raise ValueError(err_msg)

        # ctx.style_repo.favored_style_is_valid = True ensures that
        # ctx.style_repo.csl_content and ctx.style_repo.favored_style are strings
        csl_style_content: str = (
            ctx.style_repo.csl_content if ctx.style_repo.csl_content is not None else ""
        )
        target_style: str = (
            ctx.style_repo.favored_style
            if ctx.style_repo.favored_style is not None
            else ""
        )

        logger.info(
            "Formatting bibliographic structures.",
            extra={"step": self.name, "target_style": target_style},
        )
        reference_service.fill_missing_references(
            records=ctx.work_repo.records,
            doi_repo=ctx.doi_repo,
            csl_style_content=csl_style_content,
            target_style=target_style,
        )
        ctx.work_repo.save_all()
        logger.info(
            "Formatted references and updated local database.",
            extra={"step": self.name, "records_count": len(ctx.work_repo.records)},
        )


class ExportStep:
    """Pipeline step outputting structured bibliographic entries to disk."""

    name: str = "export"
    message: str = "Exporting bibliography to CSV..."

    def execute(self, ctx: PipelineContext) -> None:
        """Commit structural bibliography collections down to flat data streams."""
        logger.info(
            "Executing ExportStep: writing output files.",
            extra={"step": self.name, "output_path": str(ctx.output_filepath)},
        )
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

        logger.info(
            "Writing bibliography export payload to CSV.",
            extra={"step": self.name, "file": str(ctx.output_filepath)},
        )
        bibliography_service = BibliographyService(config=ctx.config)
        ctx.export_result = bibliography_service.export_to_csv(
            citations=ctx.citations,
            works=ctx.work_repo.records,
            output_path=ctx.output_filepath,
        )

        if ctx.export_result is not None and is_dataclass(ctx.export_result):
            style_name = ctx.style_repo.favored_style if ctx.style_repo else ctx.style
            ctx.export_result = replace(ctx.export_result, style=style_name)

        if ctx.journal_repo.records:
            ctx.anomalous_journals.clear()
            for j in ctx.journal_repo.records:
                if j.status != "OK":
                    all_found_issns = ctx.journal_repo.get_issns_by_input_title(
                        j.input_title,
                    )
                    ctx.anomalous_journals.append(
                        AnomalousJournal(
                            input_title=j.input_title,
                            status=j.status,
                            issn=j.issn or "",
                            issns_found=", ".join(all_found_issns)
                            if all_found_issns
                            else "",
                        ),
                    )
            logger.info(
                "Anomalous journals verification complete.",
                extra={
                    "step": self.name,
                    "anomalies_count": len(ctx.anomalous_journals),
                },
            )


# =============================================================================
# PIPELINE FUNCTION
# =============================================================================
def run(options: PipelineOptions) -> tuple[list[AnomalousJournal], ExportResult | None]:
    """Orchestrate the linear citation processing pipeline step-by-step."""
    app_config = options.config or get_config()
    out_path = Path(options.output_filepath) if options.output_filepath else None

    ctx = PipelineContext(
        api=options.api,
        input_file_path=str(options.input_file_path)
        if options.input_file_path
        else None,
        input_text=options.input_text,
        style=options.style,
        journal_title=options.journal_title,
        output_filepath=out_path,
        config=app_config,
        skip_journal_update=options.skip_journal_update,
        skip_work_update=options.skip_work_update,
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
            if options.progress_callback:
                options.progress_callback(
                    ProgressStep(
                        step_name=step.name,
                        current=idx,
                        total=total_steps,
                        message=step.message,
                        status="started",
                    ),
                )

            step.execute(ctx)

            if options.progress_callback:
                options.progress_callback(
                    ProgressStep(
                        step_name=step.name,
                        current=idx + 1,
                        total=total_steps,
                        message=f"Finished: {step.message}",
                        status="completed",
                    ),
                )
    finally:
        get_http_client_registry().close_all()
        get_http_client_registry.cache_clear()

    return ctx.anomalous_journals, ctx.export_result
