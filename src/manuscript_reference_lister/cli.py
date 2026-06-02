# src/manuscript_reference_lister/cli.py
import logging
import os
import sqlite3
import sys
import textwrap
import traceback
from pathlib import Path

import click

from .core import run
from .logging_config import setup_logging
from .storage.db import archive_database_cache
from .ui.progress_bar_context import ProgressBarContext
from .utils.config import get_config

logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CLI entry point for manuscript citation processing."""
    # Load config here at execution, not import
    ctx.ensure_object(dict)
    if "config" not in ctx.obj:
        ctx.obj["config"] = get_config()


@cli.command()
@click.pass_context
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
    help=("Exact journal title aimed for publication (e.g. Geomorphology)."),
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
    "-t", "--text", type=str, default=None, help="Text to parse (can also be piped)"
)
@click.option(
    "-v", "--verbose", count=True, help="Increase verbosity (-v (INFO), -vv (DEBUG))"
)
def main(
    ctx: click.Context,
    api: str,
    clear_cache: bool,
    input_file: str | None,
    journal_title: str | None,
    output_file: str | None,
    text: str | None,
    skip_journal_update: bool,
    skip_work_update: bool,
    style: str | None,
    verbose: int,
) -> None:
    """\b
    CLI entry point. Run core manuscript extraction pipeline with Click command
    configurations.
    Examples:
        # Process a file and specify output
        $ uv run python -m manuscript_reference_lister \
            -f "C:\\Documents\\manuscript.docx" -o "C:\\Documents\\bibliography.csv" \
            -s "copernicus-publications"

        Output file can be omitted, default generated file is \
            OUTPUT_DIR_PATH / "manuscript_references.csv"
        # Pipe source directly
        $ echo "Voila (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | \
            uv run python -m manuscript_reference_lister
        
        # Clear the local cache safely
        $ uv run python -m manuscript_reference_lister --clear-cache
    """
    # Force console to replace characters that can't be encoded rather than throw fatal
    if sys.platform == "win32":
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")

    click.echo("Starting manuscript-reference-lister...")

    log_dir = setup_logging(verbose_level=verbose)
    logger.info("Starting manuscript-reference-lister...")
    logger.debug("Current working directory: %s", os.getcwd())
    logger.debug("Logs are being written to: %s", str(log_dir))

    cache_summary_message = None

    try:
        config = (ctx.obj or {}).get("config") or get_config()
        config.ensure_repo_directory()

        # --- CACHE CLEARING PROCESS ---
        if clear_cache:
            click.echo("")
            click.secho(
                "⚠️  Warning: You are about to clear the local cache.",
                fg="yellow",
                bold=True,
                err=True,
            )
            click.echo(
                "This will archive your existing database local repository,"
                " forcing fresh remote API lookups."
            )

            if not click.confirm("Do you want to proceed?", default=False):
                click.echo("Operation cancelled. Cache left untouched.")
                sys.exit(0)

            db_path = Path(config.db_filepath).resolve()
            try:
                backup_path = archive_database_cache(db_path)
                if backup_path:
                    backup_name = backup_path.name
                    click.echo(f"Moved: {db_path.name} -> {backup_name}")
                    logger.info(
                        "Cache file archived: %s to %s",
                        db_path.name,
                        backup_name,
                    )
                    cache_summary_message = (
                        f"🧹 Local cache cleared (Database safely archived"
                        f" as '{backup_path}')."
                    )
                else:
                    click.secho(
                        f"⚠️  Warning: Expected cache database '{db_path.name}' "
                        f"was not found. Skipping.",
                        fg="yellow",
                    )
                    logger.warning(
                        "Cache file not found for clearing: %s", db_path.name
                    )
                    cache_summary_message = (
                        "ℹ️  No active cache database was found to clear."
                    )
            except (OSError, sqlite3.Error) as e:
                logger.error(
                    "Failed to archive cache database %s: %s",
                    str(db_path),
                    str(e),
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
                cache_summary_message = "❌ Cache clearing failed."

            click.echo("")
            click.secho(cache_summary_message, fg="green", bold=True)
            has_piped_input = not sys.stdin.isatty()
            if not input_file and not text and not has_piped_input:
                click.echo("No manuscript or text provided for processing.")
                click.echo("Done.")
                sys.exit(0)

            click.echo("Proceeding to manuscript processing with a fresh cache...\n")

        # --- STANDARD MANUSCRIPT PROCESSING ---
        if not text and not sys.stdin.isatty():
            # Read piped text with literal "\n" and "\r" converted into newline/CR bytes
            text = sys.stdin.read().strip().encode("utf-8").decode("unicode_escape")
            text = text.replace("\r", "")
        style = style if style else config.default_reference_style

        anomalies = {}
        export_metadata = None

        # ProgressBarContext handles internal log interception, threading, lock sync,
        # and silent mode when verbose > 0
        # The progressbar displays with execution time and estimated
        # time of completion (ETA)
        progress_context = ProgressBarContext(verbose_level=verbose, bar_width=30)

        with progress_context as ctx_manager:
            # Under verbose mode, ctx_manager.update is a safe no-op.
            # Under standard mode, it safely routes updates and protects stderr via its
            # inner lock.
            anomalies, export_metadata = run(
                api=api,
                input_file_path=input_file,
                input_text=text,
                output_filepath=output_file,
                config=config,
                style=style,
                journal_title=journal_title,
                progress_callback=ctx_manager.update if ctx_manager.is_active else None,
                skip_journal_update=skip_journal_update,
                skip_work_update=skip_work_update,
            )

        if cache_summary_message:
            click.echo("")
            click.secho(cache_summary_message, fg="green", bold=True)

        if skip_journal_update or skip_work_update:
            click.echo("")
            click.echo("ℹ️  Pipeline Skips:")
            if skip_journal_update:
                click.echo("   - Journal metadata update was skipped.")
            if skip_work_update:
                click.echo("   - Work DOI search and update was skipped.")
        if anomalies:
            click.echo("")
            click.secho(
                "⚠️  Warning: Some journal titles were not found, were found without"
                " an ISSN, or were found with at least one ISSN without works (these "
                "journals may have other ISSNs with works). These problematic titles"
                " or ISSNs have not been included in the search for works. "
                "This is a known limitation of the Crossref repository data structure.",
                fg="yellow",
                bold=True,
                err=True,
            )
            click.echo("", err=True)
            click.secho(
                f"{'input_title':<35} | {'issn':<10} | {'status':<20} | issns found",
                fg="cyan",
                bold=True,
                err=True,
            )
            click.secho("-" * 90, fg="cyan", err=True)

            for data in anomalies.values():
                click.echo(
                    f"{data['input_title']:<35} | {data['issn']:<10} |"
                    f" {data['status']:<20} | {data['issns_found']}",
                    err=True,
                )
            click.echo("", err=True)

        if export_metadata:
            resolved_style = export_metadata.style or ""
            style_label = f" ({resolved_style})" if resolved_style else ""

            click.echo("")
            click.secho(
                f"✨ Success: Generated and saved bibliography{style_label} with"
                f" {export_metadata.total_rows} rows "
                f"to {export_metadata.output_filepath}",
                fg="green",
                bold=True,
            )

            # Synthesis statistics
            click.echo("")
            click.secho("📊 Export Summary:", bold=True)
            click.echo(f"  • Valid references (OK)   : {export_metadata.ok_count}")
            click.echo(f"  • Missing DOI/Reference   : {export_metadata.missing_count}")
            click.echo(
                f"  • Ambiguous matches       : {export_metadata.duplicate_count}"
            )

            # CSV Preview layout construction
            preview_rows = []
            if export_metadata.sample_ok:
                preview_rows.append(export_metadata.sample_ok)
            if export_metadata.sample_missing:
                preview_rows.append(export_metadata.sample_missing)
            if export_metadata.samples_duplicate:
                preview_rows.extend(export_metadata.samples_duplicate)

            if preview_rows:
                click.echo("")
                click.secho("📝 CSV Preview:", bold=True, fg="cyan")

                col1_w, col2_w, col3_w = 25, 32, 60
                header = (
                    f"{'Citation':<{col1_w}} | {'Status':<{col2_w}} | "
                    f"{'Reference Preview':<{col3_w}}"
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
                    ref_lines = textwrap.wrap(ref_text, width=col3_w) or ["None"]

                    # First row line containing metadata elements
                    click.echo(
                        f"{row['Citation']:<{col1_w}} | "
                        f"{status_text:<{col2_w}} | "
                        f"{ref_lines[0]:<{col3_w}}"
                    )

                    # Consecutive wrapped reference lines
                    for extra_line in ref_lines[1:]:
                        click.echo(
                            f"{'':<{col1_w}} | {'':<{col2_w}} | {extra_line:<{col3_w}}"
                        )

                # Post-edition recommendations guidelines
                click.echo("")
                click.secho("💡 Next Steps & Recommendations:", bold=True, fg="yellow")

                if export_metadata.missing_count > 0:
                    click.echo(
                        "  • For citations marked as 'Missing DOI/Reference': "
                        "Please search for their DOIs\n"
                        "    manually on the Crossref website "
                        "(https://search.crossref.org) and update your records."
                    )

                if export_metadata.duplicate_count > 0:
                    click.echo(
                        "  • For citations with multiple matches: Review the "
                        "generated CSV file and delete\n"
                        "    the irrelevant reference rows, leaving only the "
                        "correct one for each citation."
                    )

                click.echo(
                    "  • Once the CSV file is cleaned and reviewed, you can directly"
                    " copy and paste\n"
                    "    the finalized reference list into your manuscript."
                )
                click.echo("")
        click.echo("Done.")

    except click.ClickException as e:
        raise e

    except Exception as e:
        logger.critical(
            "Fatal application crash encountered during execution", exc_info=True
        )

        if cache_summary_message:
            click.echo("")
            click.secho(cache_summary_message, fg="green", bold=True)

        click.echo("")
        click.secho(f"Error: An unexpected error occurred: {e}", fg="red", err=True)

        if verbose > 0:
            click.secho("\n--- Debug Traceback ---", fg="yellow", err=True)
            tb_lines = traceback.format_exception(type(e), e, e.__traceback__, limit=3)
            click.echo("".join(tb_lines), err=True)
            click.secho("-----------------------", fg="yellow", err=True)
        else:
            click.echo(
                "Use the '-v' or '-vv' option to see the full debug traceback.",
                err=True,
            )

        sys.exit(1)


if __name__ == "__main__":
    cli()
