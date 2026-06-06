# src/citecraft/parsers/html_cleaner.py
import html
import re
from html.parser import HTMLParser
from typing import override

from citecraft.utils import AppConfig, get_config


class HtmlCleaner(HTMLParser):
    """Parses and sanitizes HTML-polluted text according to a style specification."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self._config = config or get_config()

        self._preserved_tags = self._config.preserved_html_tags
        self._discarded_tags = self._config.discarded_html_tags
        self._result_parts: list[str] = []

        # Pre-compiled regular expressions for runtime efficiency
        self._whitespace_regex = re.compile(r"\s+")

        self._start_tag_space_regex = None
        self._end_tag_space_regex = None
        if self._preserved_tags:
            tags_pattern = "|".join(map(re.escape, self._preserved_tags))
            self._start_tag_space_regex = re.compile(f"<({tags_pattern})>\\s?")
            self._end_tag_space_regex = re.compile(f"\\s?</({tags_pattern})>")

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Inject preserved opening tags into the result stream."""
        if tag in self._preserved_tags:
            self._result_parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        """Inject preserved closing tags into the result stream."""
        if tag in self._preserved_tags:
            self._result_parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        """Convert non-breaking spaces and append raw text data."""
        clean_data = data.replace("\xa0", " ")
        self._result_parts.append(clean_data)

    def handle_entityref(self, name: str) -> None:
        """Resolve HTML entities to their raw Unicode representation."""
        resolved = html.unescape(f"&{name};")
        self._result_parts.append(resolved)

    def clean_to_plain_text(self, raw_reference: str) -> str:
        """Transform an HTML-polluted reference into formatted plain text.
        Extracts text, strips generic styling tags, preserves structural
        sub/superscripts, converts HTML entities back to UTF-8 characters, and
        collapses all consecutive whitespaces (including newlines) into a single space.
        """
        if not raw_reference:
            return ""

        # Buffer reset
        self._result_parts = []
        self.feed(raw_reference)
        parsed_str = "".join(self._result_parts)

        # Collapse whitespaces
        parsed_str = self._whitespace_regex.sub(" ", parsed_str)

        # Collapse internal tag spacing
        if self._preserved_tags:
            if self._start_tag_space_regex:
                parsed_str = self._start_tag_space_regex.sub(r"<\1>", parsed_str)
            if self._end_tag_space_regex:
                parsed_str = self._end_tag_space_regex.sub(r"</\1>", parsed_str)

        return parsed_str.strip()
