import html
import re
from html.parser import HTMLParser

from manuscript_reference_lister.utils.config import AppConfig, get_config


class HtmlCleaner(HTMLParser):
    """Parses and sanitizes HTML-polluted text."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self._config = config or get_config()

        self._preserved_tags = self._config.preserved_html_tags
        self._discarded_tags = self._config.discarded_html_tags
        self._result_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Callback to handle the opening of an HTML tag."""
        if tag in self._preserved_tags:
            self._result_parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        """Callback to handle the closing of an HTML tag."""
        if tag in self._preserved_tags:
            self._result_parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        """Callback to handle raw text content between or outside tags."""
        # Convert non-breaking spaces to standard spaces
        clean_data = data.replace("\xa0", " ")
        self._result_parts.append(clean_data)

    def handle_entityref(self, name: str) -> None:
        """Callback to handle HTML entities (e.g., &amp;, &quot;)."""
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

        # Normalize all spaces and newlines
        # This converts any sequence of tabs, newlines (\n), and spaces into one single standard space.
        parsed_str = re.sub(r"\s+", " ", parsed_str)

        # Collapse remaining internal tag spacing
        if self._preserved_tags:
            tags_pattern = "|".join(map(re.escape, self._preserved_tags))
            parsed_str = re.sub(f"<({tags_pattern})>\\s?", r"<\1>", parsed_str)
            parsed_str = re.sub(f"\\s?</({tags_pattern})>", r"</\1>", parsed_str)

        return parsed_str.strip()
