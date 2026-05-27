import logging
import re

logger = logging.getLogger(__name__)


class JournalParser:
    """Handles extraction of unique journal titles from marked raw text blocks."""

    def __init__(self) -> None:
        # Pre-compile regex patterns for performance optimization
        self._journals_marker_regex = re.compile(r"^Journals\s*$", re.MULTILINE)
        self._double_newline_regex = re.compile(r"\n\s*\n")

    def extract_all(self, text: str) -> list[str]:
        """Extract journal titles listed below the single-line marker 'Journals'."""
        matches = list(self._journals_marker_regex.finditer(text))

        if not matches:
            logger.warning(
                "Section marker 'Journals' not found in the provided text",
                extra={
                    "status": "KO",
                    "event": "journal_marker_missing",
                },
            )
            return []

        # Start parsing from the end of the last matched section marker
        start_index = matches[-1].end()
        remaining_text = text[start_index:]

        # Locate the terminating empty double newline boundary
        break_match = self._double_newline_regex.search(remaining_text)

        logger.debug(
            "Journal block delimited (Stop on double newline: %s)",
            bool(break_match),
            extra={
                "status": "OK",
                "event": "journal_block_delimited",
                "stopped_by_double_newline": bool(break_match),
            },
        )

        # If a break is found, take everything up to it; otherwise take the rest
        relevant_block = (
            remaining_text[: break_match.start()] if break_match else remaining_text
        )

        # Isolate lines, discard empty lines, and preserve insertion-order uniqueness
        raw_lines = (line.strip() for line in relevant_block.splitlines())
        results = list(dict.fromkeys(line for line in raw_lines if line))

        logger.info(
            "Extracted %d unique journal titles from section",
            len(results),
            extra={
                "status": "OK",
                "event": "journal_extraction_completed",
                "unique_count": len(results),
            },
        )
        return results
