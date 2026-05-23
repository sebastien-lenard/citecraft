import logging
import os
import sys
import textwrap
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import click

from .core import ProgressStep, run
from .logging_config import setup_logging
from .utils.config import get_config

logger = logging.getLogger(__name__)


class QueueHandler(logging.Handler):
    """Handler that intercepts logs to insert them above active progress bar.
    Keeps the bar visible and animated."""

    def __init__(self, draw_callback):
        super().__init__()
        self.draw_callback = draw_callback

    def emit(self, record):
        try:
            msg = self.format(record)

            # Erase current line on console and write log
            # \r = return to start of line, \033[K = erase all til the end of line
            sys.stderr.write(f"\r\033[K{msg}\n")
            sys.stderr.flush()

            # Redraw bar below log
            self.draw_callback()
        except Exception:
            self.handleError(record)


@click.group()
@click.pass_context
def cli(ctx):
    """CLI main entry point."""
    # Load config here at execution, not import
    ctx.ensure_object(dict)
    if "config" not in ctx.obj:
        ctx.obj["config"] = get_config()


@cli.command()
@click.pass_context
@click.option(
    "-f", "--input_file", type=str, default=None, help="Filepath to docx manuscript"
)
@click.option(
    "-t", "--text", type=str, default=None, help="Text to parse (can also be piped)"
)
@click.option(
    "-o",
    "--output_file",
    type=str,
    default=None,
    help="Filepath for the output Bibliography CSV",
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
    "-v", "--verbose", count=True, help="Increase verbosity (-v (INFO), -vv (DEBUG))"
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help=(
        "Safely archive local JSON cache repository files (journals and works) by"
        " renaming them."
    ),
)
def main(
    ctx,
    input_file,
    text,
    output_file,
    style,
    skip_journal_update,
    skip_work_update,
    verbose,
    clear_cache,
):
    """\b
    CLI entry point.
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
    # Force console to replace caracters that can't be encoded rather than throw fatal
    if sys.platform == "win32":
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")

    click.echo("Starting manuscript-reference-lister...")

    log_dir = setup_logging(verbose_level=verbose)
    logger.info("Starting manuscript-reference-lister...")
    logger.debug("Current working directory: %s", os.getcwd())
    logger.debug("Logs are being written to: %s", log_dir)

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
            )
            click.echo(
                "This will archive your existing journal and work local repositories,"
                " forcing fresh remote API lookups."
            )

            if not click.confirm("Do you want to proceed?", default=False):
                click.echo("Operation cancelled. Cache left untouched.")
                sys.exit(0)

            # Define cache files from configuration paths
            # (Assuming standard config structure targets: repo_dir / journals.json
            # and repo_dir / work_records.json)
            repo_path = Path(config.local_repo_dir_path)
            cache_files = [
                repo_path / "journal_records.json",  # Local journal database
                repo_path / "work_records.json",  # Local works repository
            ]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            moved_count = 0

            for cache_file in cache_files:
                if cache_file.exists():
                    backup_name = f"{cache_file.name}.bak_{timestamp}"
                    backup_path = cache_file.with_name(backup_name)
                    try:
                        cache_file.rename(backup_path)
                        click.echo(f"Moved: {cache_file.name} -> {backup_name}")
                        logger.info(
                            "Cache file archived: %s to %s",
                            cache_file.name,
                            backup_name,
                        )
                        moved_count += 1
                    except Exception as e:
                        logger.error(
                            "Failed to archive cache file %s: %s", cache_file.name, e
                        )
                        click.secho(
                            f"Error archiving {cache_file.name}: {e}",
                            fg="red",
                            err=True,
                        )
                else:
                    click.secho(
                        f"⚠️  Warning: Expected cache file '{cache_file.name}' was not"
                        f" found. Skipping.",
                        fg="yellow",
                    )
                    logger.warning(
                        "Cache file not found for clearing: %s", cache_file.name
                    )

            if moved_count > 0:
                cache_summary_message = (
                    f"🧹 Local cache cleared ({moved_count} file"
                    "(s) safely archived with suffix '.bak_{timestamp}')."
                )
            else:
                cache_summary_message = "ℹ️  No active cache files were found to clear."

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
        export_metadata = {}

        # Mode non-verbose: display of a progress bar with execution time and estimated
        # time of completion (ETA)
        if verbose == 0:
            start_global_time = time.time()

            state = {
                "message": "Initializing...",
                "current_step": 0,
                "total_steps": 4,
                "running": True,
            }

            def generate_bar_string(current, total, elapsed_time, width=30):
                percent = int((current / total) * 100) if total > 0 else 0
                filled_length = int(width * current // total) if total > 0 else 0

                fill_char = click.style("█", fg="cyan")
                empty_char = "░"
                bar = (fill_char * filled_length) + (
                    empty_char * (width - filled_length)
                )

                if current == 0 or total == 0:
                    eta_str = "--:--"
                elif current == total:
                    eta_str = "00:00"
                else:
                    remaining_steps = total - current
                    estimated_remaining_seconds = int(
                        (remaining_steps * elapsed_time) / current
                    )
                    eta_min, eta_sec = divmod(estimated_remaining_seconds, 60)
                    eta_str = f"{eta_min:02d}:{eta_sec:02d}"

                return f"[{bar}] {percent}% (ETA: {eta_str})"

            def draw_line():
                elapsed = int(time.time() - start_global_time)
                minutes, seconds = divmod(elapsed, 60)
                time_str = f"[{minutes:02d}:{seconds:02d}]"

                bar_text = generate_bar_string(
                    state["current_step"], state["total_steps"], elapsed
                )
                full_line = f"\r\033[K{time_str} {state['message']:<55} {bar_text}"

                sys.stderr.write(full_line)
                sys.stderr.flush()

            # --- INJECTION OF LOGGING HANDLER ---
            root_logger = logging.getLogger()
            # Temporary removal of default handlers to prevent duplicate logs
            old_handlers = root_logger.handlers[:]
            for h in old_handlers:
                root_logger.removeHandler(h)

            custom_handler = QueueHandler(draw_callback=draw_line)
            custom_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            root_logger.addHandler(custom_handler)

            # BACKGROUND TIMER THREAD
            def timer_ticker():
                while state["running"]:
                    draw_line()
                    time.sleep(1.0)

            ticker_thread = threading.Thread(target=timer_ticker, daemon=True)
            ticker_thread.start()

            # MAIN THREAD CALLBACK
            def cli_progress_handler(step: ProgressStep):
                state["message"] = step.message
                state["total_steps"] = step.total
                if step.status == "completed":
                    state["current_step"] = step.current
                    draw_line()

            success = False
            try:
                anomalies, export_metadata = run(
                    input_file_path=input_file,
                    input_text=text,
                    output_filepath=output_file,
                    config=config,
                    style=style,
                    progress_callback=cli_progress_handler,
                    skip_journal_update=skip_journal_update,
                    skip_work_update=skip_work_update,
                )
                success = True
            finally:
                # Cut thread to freeze display
                state["running"] = False
                ticker_thread.join(timeout=1.0)

                if success:
                    state["current_step"] = state["total_steps"]
                    state["message"] = "Completed."
                    draw_line()
                    sys.stderr.write("\n")
                else:
                    # Crash: force end of line to free the progress bar line before
                    # traceback print
                    sys.stderr.write("\n")
                sys.stderr.flush()

                # Restauration of original handlers for safety
                root_logger.removeHandler(custom_handler)
                for h in old_handlers:
                    root_logger.addHandler(h)
        else:
            anomalies, export_metadata = run(
                input_file_path=input_file,
                input_text=text,
                output_filepath=output_file,
                config=config,
                style=style,
                progress_callback=None,
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
            click.echo("")
            click.secho(
                f"✨ Success: Generated and saved bibliography with"
                f" {export_metadata.total_rows} rows "
                f"to {export_metadata.output_filepath}",
                fg="green",
                bold=True,
            )

            # 1. Affichage des statistiques de synthèse
            click.echo("")
            click.secho("📊 Export Summary:", bold=True)
            click.echo(f"  • Valid references (OK)   : {export_metadata.ok_count}")
            click.echo(f"  • Missing DOI/Reference   : {export_metadata.missing_count}")
            click.echo(
                f"  • Ambiguous matches       : {export_metadata.duplicate_count}"
            )

            # 2. Construction de la section "CSV Preview"
            # On rassemble les échantillons disponibles dans l'ordre (OK, puis Missing, puis Duplicates)
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

                # Définition des largeurs fixes de colonnes
                col1_w, col2_w, col3_w = 25, 32, 60
                header = f"{'Citation':<{col1_w}} | {'Status':<{col2_w}} | {'Reference Preview':<{col3_w}}"

                click.secho(header, fg="cyan", bold=True)
                click.secho("-" * len(header), fg="cyan")

                for row in preview_rows:
                    # Simplification des statuts pour le tableau
                    status_text = row.get("Status", "")
                    if "No doi or reference" in status_text:
                        status_text = "Warning: Missing metadata"
                    elif "select the right reference" in status_text:
                        status_text = "Warning: Multiple matches"

                    ref_text = row.get("Reference") or "None"

                    # Découpage automatique de la référence en morceaux de 60 caractères max
                    ref_lines = textwrap.wrap(ref_text, width=col3_w) or ["None"]

                    # Première ligne : contient la Citation, le Statut et le début de la Référence
                    click.echo(
                        f"{row['Citation']:<{col1_w}} | "
                        f"{status_text:<{col2_w}} | "
                        f"{ref_lines[0]:<{col3_w}}"
                    )

                    # Lignes suivantes : on laisse les deux premières colonnes vides
                    for extra_line in ref_lines[1:]:
                        click.echo(
                            f"{'':<{col1_w}} | {'':<{col2_w}} | {extra_line:<{col3_w}}"
                        )

                # 3. Messages informatifs d'aide à la post-édition
                click.echo("")
                click.secho("💡 Next Steps & Recommendations:", bold=True, fg="yellow")

                if export_metadata.missing_count > 0:
                    click.echo(
                        "  • For citations marked as 'Missing DOI/Reference': Please search for their DOIs\n"
                        "    manually on the Crossref website (https://search.crossref.org) and update your records."
                    )

                if export_metadata.duplicate_count > 0:
                    click.echo(
                        "  • For citations with multiple matches: Review the generated CSV file and delete\n"
                        "    the irrelevant reference rows, leaving only the correct one for each citation."
                    )

                click.echo(
                    "  • Once the CSV file is cleaned and reviewed, you can directly copy and paste\n"
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
            # If -v or -vv activated, traceback printed
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
