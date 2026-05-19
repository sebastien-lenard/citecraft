import logging
import os
import sys
import traceback

import click

from .core import run
from .logging_config import setup_logging
from .utils.config import get_config

logger = logging.getLogger(__name__)


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
    "-v", "--verbose", count=True, help="Increase verbosity (-v (INFO), -vv (DEBUG))"
)
def main(ctx, input_file, text, output_file, verbose):
    """\b
    CLI entry point.
    Examples:
        # Process a file and specify output
        $ uv run python -m manuscript_reference_lister \
            --f "C:\\Documents\\manuscript.docx" -o "C:\\Documents\\bibliography.csv"

        Output file can be omitted, default generated file is \
            OUTPUT_DIR_PATH / "manuscript_references.csv"
        # Pipe source directly
        $ echo "Voila (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | \
            uv run python -m manuscript_reference_lister
    """

    log_dir = setup_logging(verbose_level=verbose)

    logger.info("Starting manuscript-reference-lister...")
    logger.debug("Current working directory: %s", os.getcwd())
    logger.debug("Logs are being written to: %s", log_dir)

    if not text and not sys.stdin.isatty():
        # Read piped text with literal "\n" and "\r" converted into newline/CR bytes
        text = sys.stdin.read().strip().encode("utf-8").decode("unicode_escape")
        text = text.replace("\r", "")

    try:
        config = (ctx.obj or {}).get("config") or get_config()
        config.ensure_repo_directory()

        anomalies = run(
            input_file_path=input_file,
            input_text=text,
            output_filepath=output_file,
            config=config,
        )

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
        click.echo("Done.")

    except click.ClickException as e:
        raise e

    except Exception as e:
        logger.critical(
            "Fatal application crash encountered during execution", exc_info=True
        )

        click.secho(f"\nError: An unexpected error occurred: {e}", fg="red", err=True)

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
