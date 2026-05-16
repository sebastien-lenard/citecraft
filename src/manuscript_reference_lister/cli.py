import logging
import os
import sys
import traceback

import click

from .core import run

logger = logging.getLogger("manuscript_reference_lister.cli")


@click.command()
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
def main(input_file, text, output_file, verbose):
    """\b
    CLI entry point.
    Examples:
        # Process a file and specify output
        $ uv run python -m src.manuscript_reference_lister \
            --f "C:\\Documents\\manuscript.docx" -o "C:\\Documents\\bibliography.csv"

        Output file can be omitted, default generated file is \
            OUTPUT_DIR_PATH / "manuscript_references.csv"
        # Pipe source directly
        $ echo "Voila (Lenard et al., 2020)\r\nJournals\r\nNature Geoscience" | \
            uv run python -m src.manuscript_reference_lister
    """

    levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    log_level = levels.get(verbose, logging.DEBUG)
    logging.basicConfig(
        level=log_level, format="%(levelname)s [%(name)s]: %(message)s", force=True
    )

    logger.info("Starting manuscript-reference-lister...")
    logger.debug("Current working directory: %s", os.getcwd())

    if not text and not sys.stdin.isatty():
        # Read piped text with literal "\n" and "\r" converted into newline/CR bytes
        text = sys.stdin.read().strip().encode("utf-8").decode("unicode_escape")
        text = text.replace("\r", "")

    try:
        run(input_file_path=input_file, input_text=text, output_filepath=output_file)
        click.echo("Done.")

    except click.ClickException as e:
        raise e

    except Exception as e:
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
    main()
