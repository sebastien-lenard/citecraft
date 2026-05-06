import logging
import re


class JournalParser:
    """Handles extraction of journal titles from raw text."""

    def extract_all(self, text: str) -> list[str]:
        """Extract journal titles in a text. The titles should be positioned below a
        line containing only the text Journals, and separated by an EOL."""
        # Matches "Journals" only if it is the only word on the line
        # re.MULTILINE makes ^ and $ work per line
        matches = list(re.finditer(r"^Journals\s*$", text, re.MULTILINE))

        if not matches:
            return []

        # Start from the end of the last "Journals" match
        start_index = matches[-1].end()
        remaining_text = text[start_index:]

        # Look for the first occurrence of two newlines (the "break")
        # \n\s*\n matches a newline, any whitespace/tabs, then another newline
        break_match = re.search(r"\n\s*\n", remaining_text)

        # If a break is found, take everything up to it; otherwise take the rest
        relevant_block = (
            remaining_text[: break_match.start()] if break_match else remaining_text
        )

        # Split into lines, strip whitespace, and filter out empty strings
        results = [line.strip() for line in relevant_block.splitlines() if line.strip()]
        results = list(dict.fromkeys(results))  # unique titles
        logging.info(f"Parsed {len(results)} unique journal titles.")
        return results
