import html
import re
from html.parser import HTMLParser


class HtmlCleaner(HTMLParser):
    """Parses and sanitizes HTML-polluted text."""

    def __init__(self) -> None:
        super().__init__()
        # Structural tags to explicitly preserve in the final output record
        self._preserved_tags = {"sup", "sub"}
        # Styling tags whose inner text is kept but boundaries are discarded
        self._discarded_tags = {"i", "b", "strong", "u", "small"}

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

    @classmethod
    def clean_to_plain_text(cls, raw_reference: str) -> str:
        """Transform an HTML-polluted reference into formatted plain text.
        Extracts text, strips generic styling tags, preserves structural
        sub/superscripts, converts HTML entities back to UTF-8 characters, and
        collapses all consecutive whitespaces (including newlines) into a single space.
        """
        if not raw_reference:
            return ""

        # Step 1: Parse the HTML structure and filter tags
        parser = cls()
        parser.feed(raw_reference)
        parsed_str = "".join(parser._result_parts)

        # Step 2: Normalize all spaces and newlines
        # This converts any sequence of tabs, newlines (\n), and spaces into one single standard space.
        parsed_str = re.sub(r"\s+", " ", parsed_str)

        # Step 3: Collapse internal tag spacing (e.g., "<sub>  w  </sub>" -> "<sub>w</sub>")
        # Since Step 2 reduced everything to single spaces, we only need to handle a single optional space.
        parsed_str = re.sub(r"<(sup|sub)>\s?", r"<\1>", parsed_str)
        parsed_str = re.sub(r"\s?</(sup|sub)>", r"</\1>", parsed_str)

        return parsed_str.strip()
