# src/citecraft/parsers/citation_parser.py
import logging
import re

from citecraft.schemas import CitationMetadata
from citecraft.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


class CitationParser:
    """Handles extraction of narrative and parenthetical academic citations from raw text."""

    def __init__(
        self,
        blacklist: list[str] | None = None,
        config: AppConfig | None = None,
    ) -> None:
        # Extended blacklist to avoid confusion with figures/tables
        config = config or get_config()
        self.blacklist: list[str] = blacklist or config.parser_blacklist

        # Unicode and standard dash ranges
        dash_range = r"-\u2010-\u2015"
        dash_class = rf"[{dash_range}]"

        # LOGIC:
        # 1. Particles: (Van Der | van der | De) - Optional
        # 2. Initials: (A. or A.B. or A.B-C.) - Optional
        # 3. Last Name: (Lénard or Lyon-Caen) - Mandatory
        # 4. Optional suffix: ( et al. | and Name | et Name)

        particles = r"(?:(?:[Vv]an\s+[Dd]er\s+)|(?:De\s+))?"
        # initials handles: S. or J.S. or S.J-P. (no space required between dots)
        initials = rf"(?:[A-Z]\.[A-Z\.{dash_range}]*(?=\s+))"
        # last_name handles: Lénard, Lyon-Caen, or Van Asch (if space)
        last_name = (
            rf"[A-Z][a-zÀ-ÿ]*(?:{dash_class}[A-Z][a-zÀ-ÿ]*)*(?:\s+[A-Z][a-zÀ-ÿ]+)?"
        )

        name_with_initials = rf"{particles}{initials}\s+{last_name}"
        name_without_initials = rf"{particles}{last_name}"
        name_unit = rf"(?:{name_with_initials}|{name_without_initials})"

        # Author pattern logic:
        # Matches Author (monograph), Author et al., or Author and/et Author
        self.author_pattern: str = (
            rf"{name_unit}(?:\s+et\s+al\.|(?:\s+(?:and|et)\s+{name_unit}))?"
        )

        # Matches years 1600-2099 optionally followed by a single character suffix
        self.year_pattern: str = r"\b(?:16|17|18|19|20)\d{2}[a-z]?\b"

        # Pre-compiled regular expressions for runtime efficiency
        self._narrative_regex = re.compile(
            rf"({self.author_pattern})\s*\((({self.year_pattern})(?:,\s*{self.year_pattern})*)\)"
        )
        self._year_regex = re.compile(self.year_pattern)
        self._author_comma_regex = re.compile(rf"({self.author_pattern})\s*,")

        # Pre-compiled blacklist search and replace patterns
        self._blacklist_search = {
            word: re.compile(rf"\b{word}\b", flags=re.IGNORECASE)
            for word in self.blacklist
        }
        self._blacklist_replace = {
            word: re.compile(rf"\b{word}\b[. ,]*", flags=re.IGNORECASE)
            for word in self.blacklist
        }

    def is_blacklisted(self, word: str) -> bool:
        """Check if a word matches any element in the configured blacklist."""
        clean_word = re.sub(r"[.,;]", "", word)
        return clean_word in self.blacklist

    def extract_all(self, text: str) -> list[CitationMetadata]:
        """Extract narrative and parenthetical citations from raw text strings.
        Extract narrative (e.g. Hamling (2020)) and parenthetical (e.g. (Lenard et al.,
        2020)) citations (can be duplicates).
        Handles complex cases:
        - multiple years (Hovius et al., 1997, 2011)
        - multiple citations (Jeandet et al., 2019; Lenard et al., 2020)
        - suffixes (Lenard et al., 2020a)
        - initials (S.J.P. Lenard et al., 2020)
        - dashes (Lyon-Caen) and accents
        - single author (Hamling(2020))
        - two authors (Densmore and Hovius, 2020)
        - French et (Densmore et Hovius, 2020)
        - citations with ancillary words (blacklist, e.g. Fig., see, Table)
        - don't capture isolated years (e.g. (2020)) or dates (March 6, 2020)
        """
        results: list[CitationMetadata] = []

        # 1. NARRATIVE CITATIONS: Hovius et al. (1997, 1999)
        # Handles one or multiple years inside the parentheses following an author.
        for match in self._narrative_regex.finditer(text):
            author_name = match.group(1).strip()
            # Capture all years listed (e.g., ['2017', '2019'])
            years = self._year_regex.findall(match.group(2))
            for y in years:
                results.append(
                    CitationMetadata(
                        first_authors_txt=author_name,
                        year_and_suffix=y.strip(),
                        type="narrative",
                    )
                )

        # 2. PARENTHETICAL CITATIONS: (Hovius et al., 1997; Parker and Smith, 2011)
        # First, extract everything inside parentheses
        paren_blocks = re.findall(r"\(([^)]+)\)", text)
        for block in paren_blocks:
            # Split the block by semicolon to isolate different reference groups
            groups = block.split(";")
            for group in groups:
                clean_group = group.strip()
                # Optimize search & replace via pre-compiled regex structures
                for word in self.blacklist:
                    if self._blacklist_search[word].search(clean_group):
                        previous_group = clean_group
                        clean_group = self._blacklist_replace[word].sub("", clean_group)
                        logger.debug(
                            "Blacklist word '%s' stripped from parenthetical group",
                            word,
                            extra={
                                "status": "OK",
                                "event": "parser_blacklist_match",
                                "word": word,
                                "before": previous_group,
                                "after": clean_group,
                            },
                        )

                # Requirement: Group must contain an author pattern followed by year(s).
                # This prevents capturing isolated dates like (2020) or (in 2020).
                author_match = self._author_comma_regex.search(clean_group)
                if author_match:
                    author_name = author_match.group(1).strip()
                    years = self._year_regex.findall(clean_group)
                    for y in years:
                        results.append(
                            CitationMetadata(
                                first_authors_txt=author_name,
                                year_and_suffix=y,
                                type="parenthetical",
                            )
                        )

        logger.info(
            "Extracted %d raw citations from text",
            len(results),
            extra={
                "status": "OK",
                "event": "citation_extraction_completed",
                "raw_count": len(results),
            },
        )
        return results
