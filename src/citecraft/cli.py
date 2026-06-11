# src/citecraft/cli.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""CLI entry point for manuscript citation processing."""

import io
import logging
import sqlite3
import sys
import textwrap
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import click

from .core import AnomalousJournal, PipelineOptions, run
from .logging_config import setup_logging
from .logging_infra.progress_bar_context import ProgressBarContext
from .schemas import BibliographyResult
from .storage.db import archive_database_cache
from .ui.app import CiteCraftApp
from .utils import AppConfig
from .utils.config import get_config

logger = logging.getLogger(__name__)

# Core layout configuration constraints
COL1_W: Final[int] = 25
COL2_W: Final[int] = 32
COL3_W: Final[int] = 60


@dataclass(slots=True, frozen=True)
class ProcessedArgs:
    """Strongly-typed parameter container to satisfy PLR0913 constraint limits."""

    api: str
    input_file: str | None
    journal_title: str | None
    output_file: str | None
    skip_journal_update: bool
    skip_work_update: bool
    style: str | None
    text: str | None
    verbose: int


# ==============================================================================
# 1. PLATFORM & INPUT HELPERS
# ==============================================================================


def _configure_windows_console() -> None:
    """Force Windows console to replace unencodable characters instead of crashing."""
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding=sys.stdout.encoding,
            errors="replace",
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding=sys.stderr.encoding,
            errors="replace",
        )


def _read_piped_input() -> str:
    """Extract and sanitize piped input text from stdin streams safely."""
    if sys.stdin.isatty():
        return ""

    valid_text = sys.stdin.read().strip().encode("utf-8").decode("unicode_escape")
    return valid_text.replace("\r", "")


# ==============================================================================
# 2. UI PRESENTATION ENGINE (DELEGATED RENDERERS)
# ==============================================================================


def _render_anomalous_journals(anomalous_journals: list[AnomalousJournal]) -> None:
    """Print an aligned, structured table detailing repository journals in anomaly."""
    if not anomalous_journals:
        return

    click.echo("")
    click.secho(
        "⚠️ Warning: Some journal titles were not found, were found without"
        " an ISSN, or were found with at least one ISSN without works (these "
        "journals may have other ISSNs with works). These problematic titles"
        " or ISSNs have not been included in the search for works. "
        "This is a known limitation of the Crossref repository data structure.",
        fg="yellow",
        bold=True,
        err=True,
    )
    click.echo("", err=True)

    header = f"{'input_title':<35} | {'issn':<10} | {'status':<20} | issns found"
    click.secho(header, fg="cyan", bold=True, err=True)
    click.secho("-" * 90, fg="cyan", err=True)

    for journal in anomalous_journals:
        click.echo(
            f"{journal.input_title:<35} | {journal.issn:<10} |"
            f" {journal.status:<20} | {journal.issns_found}",
            err=True,
        )
    click.echo("", err=True)


def _render_export_summary(metadata: BibliographyResult) -> None:
    """Display structural statistics and KPIs for the generated export."""
    resolved_style = metadata.style or ""
    style_label = f" ({resolved_style})" if resolved_style else ""

    click.echo("")
    click.secho(
        f"✨ Success: Generated and saved bibliography{style_label} with"
        f" {metadata.total_rows} rows "
        f"to {metadata.output_filepath}",
        fg="green",
        bold=True,
    )
    click.echo("")
    click.secho("📊 Export Summary:", bold=True)
    click.echo(f"  • Valid references (OK)   : {metadata.ok_count}")
    click.echo(f"  • Missing DOI/Reference   : {metadata.missing_count}")
    click.echo(f"  • Ambiguous matches       : {metadata.duplicate_count}")


def _render_csv_preview(metadata: BibliographyResult) -> None:
    """Construct and print a neatly wrapped ASCII table preview of the CSV."""
    preview_rows: list[dict[str, str]] = []
    if metadata.sample_ok:
        preview_rows.append(metadata.sample_ok)
    if metadata.sample_missing:
        preview_rows.append(metadata.sample_missing)
    if metadata.samples_duplicate:
        preview_rows.extend(metadata.samples_duplicate)

    if not preview_rows:
        return

    click.echo("")
    click.secho("📝 CSV Preview:", bold=True, fg="cyan")

    header = (
        f"{'Citation':<{COL1_W}} | "
        f"{'Status':<{COL2_W}} | "
        f"{'Reference Preview':<{COL3_W}}"
    )
    click.secho(header, fg="cyan", bold=True)
    click.secho("-" * len(header), fg="cyan")

    for row in preview_rows:
        status_text = row.get("Status", "")
        if "No doi or reference" in status_text:
            status_text = "Warning: Missing metadata"
        elif "select the right reference" in status_text:
            status_text = "Warning: Multiple matches"

        ref_text = row.get("Reference") or "None"
        ref_lines = textwrap.wrap(ref_text, width=COL3_W) or ["None"]

        click.echo(
            f"{row['Citation']:<{COL1_W}} | "
            f"{status_text:<{COL2_W}} | "
            f"{ref_lines[0]:<{COL3_W}}",
        )

        for extra_line in ref_lines[1:]:
            click.echo(f"{'':<{COL1_W}} | {'':<{COL2_W}} | {extra_line:<{COL3_W}}")


def _render_recommendations(metadata: BibliographyResult) -> None:
    """Provide contextual next-steps action items based on output composition."""
    click.echo("")
    click.secho("💡 Next Steps & Recommendations:", bold=True, fg="yellow")

    if metadata.missing_count > 0:
        click.echo(
            "  • For citations marked as 'Missing DOI/Reference': "
            "Please search for their DOIs\n"
            "    manually on the Crossref website "
            "(https://search.crossref.org) and update your records.",
        )

    if metadata.duplicate_count > 0:
        click.echo(
            "  • For citations with multiple matches: "
            "Review the generated CSV file and delete\n"
            "    the irrelevant reference rows, leaving only the "
            "correct one for each citation.",
        )

    click.echo(
        "  • Once the CSV file is cleaned and reviewed, you can directly"
        " copy and paste\n"
        "    the finalized reference list into your manuscript.",
    )
    click.echo("")


def _handle_execution_failure(
    err: Exception,
    verbose: int,
    cache_msg: str | None,
) -> None:
    """Log the failure securely and output clear terminal diagnostics."""
    logger.error(
        "Fatal application crash encountered during execution",
        exc_info=err,
    )

    if cache_msg:
        click.echo("")
        click.secho(cache_msg, fg="green", bold=True)

    click.echo("")
    click.secho(f"Error: An unexpected error occurred: {err}", fg="red", err=True)

    if verbose > 0:
        click.secho("\n--- Debug Traceback ---", fg="yellow", err=True)
        tb_lines = traceback.format_exception(err, limit=3)
        click.echo("".join(tb_lines), err=True)
        click.secho("-----------------------", fg="yellow", err=True)
    else:
        click.echo(
            "Use the '-v' or '-vv' option to see the full debug traceback.",
            err=True,
        )
    sys.exit(1)


# ==============================================================================
# 3. ISOLATED BUSINESS RUNNER (SOLVES C901 COMPLETELY)
# ==============================================================================


def _execute_processing_pipeline(
    config: AppConfig,
    p_args: ProcessedArgs,
    cache_summary_message: str | None,
) -> None:
    """Isolate runtime pipeline logic execution from Click decorator syntax."""
    valid_text = p_args.text or _read_piped_input()
    favored_style = p_args.style or config.default_reference_style

    if not p_args.input_file and not valid_text:
        click.echo("No manuscript file or raw text provided.\nDone.")
        return

    try:
        config.ensure_repo_directory()
        progress_context = ProgressBarContext(
            verbose_level=p_args.verbose,
            bar_width=30,
        )

        with progress_context as ctx_manager:
            anomalous_journals, export_metadata = run(
                PipelineOptions(
                    api=p_args.api,
                    input_file_path=p_args.input_file,
                    input_text=valid_text,
                    output_filepath=p_args.output_file,
                    config=config,
                    style=favored_style,
                    journal_title=p_args.journal_title,
                    progress_callback=(
                        ctx_manager.update if ctx_manager.is_active else None
                    ),
                    skip_journal_update=p_args.skip_journal_update,
                    skip_work_update=p_args.skip_work_update,
                ),
            )

        if cache_summary_message:
            click.echo("")
            click.secho(cache_summary_message, fg="green", bold=True)

        if p_args.skip_journal_update or p_args.skip_work_update:
            click.echo("")
            click.echo("ℹ️ Pipeline Skips:")
            if p_args.skip_journal_update:
                click.echo("   - Journal metadata update was skipped.")
            if p_args.skip_work_update:
                click.echo("   - Work DOI search and update was skipped.")

        _render_anomalous_journals(anomalous_journals)
        if export_metadata:
            _render_export_summary(export_metadata)
            _render_csv_preview(export_metadata)
            _render_recommendations(export_metadata)

        click.echo("Done.")

    except click.ClickException:
        raise
    except Exception as e:  # noqa: BLE001
        # Explicit Exception catch authorized for global interface wrapper sanitization
        _handle_execution_failure(e, p_args.verbose, cache_summary_message)


# ==============================================================================
# 4. INTERFACE CONTROLLERS & ENTRY ROUTERS
# ==============================================================================


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--gui",
    is_flag=True,
    help="Launch the modern desktop CustomTkinter GUI wrapper.",
)
@click.option(
    "-a",
    "--api",
    default="OpenAlex",
    show_default=True,
    help=(
        "Favored REST API for work DOI matching. Choice of `Crossref` or `OpenAlex`."
    ),
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help=(
        "Safely archive local SQLite cache database file by renaming it with a"
        " timestamp backup suffix."
    ),
)
@click.option(
    "-f",
    "--input-file",
    "--input_file",
    type=str,
    default=None,
    help="Filepath to docx manuscript",
)
@click.option(
    "-j",
    "--journal-title",
    "--journal_title",
    default=None,
    help="Exact journal title aimed for publication (e.g. Geomorphology).",
)
@click.option(
    "-o",
    "--output-file",
    "output_file",
    type=str,
    default=None,
    help="Filepath for the output Bibliography CSV",
)
@click.option(
    "--skip-journal-update",
    is_flag=True,
    help="Skip fetching updates for journal records from the remote API.",
)
@click.option(
    "--skip-work-update",
    is_flag=True,
    help="Skip fetching and updating work records from remote API.",
)
@click.option(
    "-s",
    "--style",
    default=None,
    show_default=True,
    help=(
        "Style name recognized by https://citation.doi.org/ (e.g., apa, "
        "copernicus-publications)."
    ),
)
@click.option(
    "-t",
    "--text",
    type=str,
    default=None,
    help="Text to parse (can also be piped)",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v (INFO), -vv (DEBUG))",
)
def cli(ctx: click.Context, **kwargs: object) -> None:
    """CLI entry point for manuscript citation processing."""
    _configure_windows_console()
    ctx.ensure_object(dict)
    if "config" not in ctx.obj:
        ctx.obj["config"] = get_config()

    # Intercept --gui option right at the root entrypoint
    if kwargs.get("gui"):
        logger.info("Bootstrapping modern CustomTkinter desktop UI wrapper.")
        app = CiteCraftApp()
        app.mainloop()
        sys.exit(0)

    # Intercept --clear-cache right at the root entrypoint
    if kwargs.get("clear_cache"):
        ctx.forward(clear_cache_command)
        return

    # If no nested command was called (like 'cache clear'), run manuscript processing
    if ctx.invoked_subcommand is None:
        ctx.invoke(process_command, **kwargs)


@cli.group(name="cache")
def cache_group() -> None:
    """Administrative commands for managing the local database cache."""


@cache_group.command(name="clear")
@click.pass_context
def clear_cache_command(ctx: click.Context, **_kwargs: object) -> None:
    """Safely archive local SQLite cache database file by renaming it."""
    config = ctx.obj["config"]

    click.echo("")
    click.secho(
        "⚠️ Warning: You are about to clear the local cache.",
        fg="yellow",
        bold=True,
        err=True,
    )
    click.echo(
        "This will archive your existing database local repository,"
        " forcing fresh remote API lookups.",
    )

    if not click.confirm("Do you want to proceed?", default=False):
        click.echo("Operation cancelled. Cache left untouched.")
        sys.exit(0)

    db_path = Path(config.db_filepath).resolve()
    try:
        config.ensure_repo_directory()
        backup_path = archive_database_cache(db_path)
        if backup_path:
            backup_name = backup_path.name
            click.echo(f"Moved: {db_path.name} -> {backup_name}")
            logger.info(
                "Cache file archived: %s to %s",
                db_path.name,
                backup_name,
            )
            click.echo("")
            click.secho(
                f"🧹 Local cache cleared (Database safely archived"
                f" as '{backup_path}').",
                fg="green",
                bold=True,
            )
        else:
            click.secho(
                f"⚠️ Warning: Expected cache database '{db_path.name}' "
                f"was not found. Skipping.",
                fg="yellow",
            )
            logger.warning("Cache file not found for clearing: %s", db_path.name)
            click.echo("")
            click.secho(
                "ℹ️ No active cache database was found to clear.",
                fg="green",
                bold=True,
            )
    except (OSError, sqlite3.Error) as e:
        logger.exception(
            "Failed to archive cache database %s.",
            str(db_path),
        )
        logger.debug(
            "Detailed traceback for database archive failure:",
            exc_info=True,
        )
        click.secho(
            f"Error archiving {db_path.name}: {e}",
            fg="red",
            err=True,
        )
        click.echo("")
        click.secho("❌ Cache clearing failed.", fg="green", bold=True)
        sys.exit(1)

    click.echo("Done.")
    sys.exit(0)


@cli.command(name="process")
@click.pass_context
def process_command(ctx: click.Context, **kwargs: object) -> None:
    """Run core manuscript extraction pipeline with Click configurations."""
    click.echo("Starting citecraft...")
    config = ctx.obj["config"]

    raw_api = kwargs.get("api")
    raw_input_file = kwargs.get("input_file")
    raw_journal_title = kwargs.get("journal_title")
    raw_output_file = kwargs.get("output_file")
    raw_skip_journal = kwargs.get("skip_journal_update")
    raw_skip_work = kwargs.get("skip_work_update")
    raw_style = kwargs.get("style")
    raw_text = kwargs.get("text")
    raw_verbose = kwargs.get("verbose")

    api_val: str = str(raw_api) if raw_api is not None else "OpenAlex"
    input_file_val: str | None = (
        raw_input_file if isinstance(raw_input_file, str) else None
    )
    journal_title_val: str | None = (
        raw_journal_title if isinstance(raw_journal_title, str) else None
    )
    output_file_val: str | None = (
        raw_output_file if isinstance(raw_output_file, str) else None
    )
    skip_journal_val: bool = bool(raw_skip_journal)
    skip_work_val: bool = bool(raw_skip_work)
    style_val: str | None = raw_style if isinstance(raw_style, str) else None
    text_val: str | None = raw_text if isinstance(raw_text, str) else None
    verbose_val: int = int(raw_verbose) if isinstance(raw_verbose, int) else 0

    p_args = ProcessedArgs(
        api=api_val,
        input_file=input_file_val,
        journal_title=journal_title_val,
        output_file=output_file_val,
        skip_journal_update=skip_journal_val,
        skip_work_update=skip_work_val,
        style=style_val,
        text=text_val,
        verbose=verbose_val,
    )

    # Configure Logging Infrastructure Context
    log_dir, intended_dir, is_fallback = setup_logging(verbose_level=p_args.verbose)
    logger.debug("Current working directory: %s", Path.cwd())
    logger.debug("Logs are being written to: %s", str(log_dir))
    if is_fallback:
        logger.debug("⚠️ Warning: Could not create directory at '%s'.", intended_dir)
        logger.debug("   Falling back to temporary storage: '%s'", log_dir)
    else:
        logger.debug("Logs are being written to: %s", str(log_dir))

    cache_summary_message: str | None = None

    _execute_processing_pipeline(config, p_args, cache_summary_message)


if __name__ == "__main__":
    cli()
