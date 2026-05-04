import re

from manuscript_reference_lister import config_loader
from manuscript_reference_lister.schemas import CitationMetadata


class CitationParser:
    """Handles extraction of citations from raw text."""

    def __init__(self, blacklist=None):
        # Extended blacklist to avoid confusion with figures/tables
        self.blacklist = blacklist or config_loader.PARSER_DEFAULT_BLACKLIST

        # Universal dash handling (standard, unicode 2010-2015)
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
        # Matches: Author (monograph), Author et al., or Author and/et Author
        self.author_pattern = (
            rf"{name_unit}(?:\s+et\s+al\.|(?:\s+(?:and|et)\s+{name_unit}))?"
        )

        # Matches: 1997 OR 1997a, extended to (1600-2099)
        self.year_pattern = r"\b(?:16|17|18|19|20)\d{2}[a-z]?\b"

    def is_blacklisted(self, word: str) -> bool:
        """Check if a word is in the blacklist using strict matching."""
        clean_word = re.sub(r"[.,;]", "", word)
        return clean_word in self.blacklist

    def extract_all(self, text: str) -> list[CitationMetadata]:
        """
        Extract narrative (e.g. Hamling (2020)) and parenthetical (e.g. (Lenard et al.,
        2020)) citations.
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
        results = []

        # 1. NARRATIVE CITATIONS: Hovius et al. (1997, 1999)
        # Handles one or multiple years inside the parentheses following an author.
        narrative_regex = (
            rf"({self.author_pattern})\s*"
            rf"\((({self.year_pattern})(?:,\s*{self.year_pattern})*)\)"
        )

        for match in re.finditer(narrative_regex, text):
            author_name = match.group(1).strip()
            # Capture all years listed (e.g., ['2017', '2019'])
            years = re.findall(self.year_pattern, match.group(2))
            for y in years:
                results.append(
                    {
                        "first_authors_txt": author_name,
                        "year_and_suffix": y.strip(),
                        "type": "narrative",
                    }
                )

        # 2. PARENTHETICAL CITATIONS: (Hovius et al., 1997; Parker and Smith, 2011)
        # First, extract everything inside parentheses
        paren_blocks = re.findall(r"\(([^)]+)\)", text)
        for block in paren_blocks:
            # Split the block by semicolon to isolate different reference groups
            groups = block.split(";")
            for group in groups:
                clean_group = group.strip()
                # Clean the group of blacklist words
                for word in self.blacklist:
                    clean_group = re.sub(
                        rf"\b{word}\b[. ,]*", "", clean_group, flags=re.IGNORECASE
                    )

                # Requirement: Group must contain an author pattern followed by year(s).
                # This prevents capturing isolated dates like (2020) or (in 2020).
                author_match = re.search(rf"({self.author_pattern})\s*,", clean_group)
                if author_match:
                    author_name = author_match.group(1).strip()
                    years = re.findall(f"({self.year_pattern})", clean_group)
                    for y in years:
                        results.append(
                            {
                                "first_authors_txt": author_name,
                                "year_and_suffix": y,
                                "type": "parenthetical",
                            }
                        )

        return self._deduplicate(results)

    def _deduplicate(self, citations: list[CitationMetadata]) -> list[CitationMetadata]:
        """Remove duplicates (independently from type)."""
        seen = set()
        unique_citations = []
        for c in citations:
            identifier = (c["first_authors_txt"], c["year_and_suffix"])
            if identifier not in seen:
                seen.add(identifier)
                unique_citations.append(c)
        return unique_citations
