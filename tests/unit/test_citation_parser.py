import pytest

from manuscript_reference_lister.parsers import CitationParser


@pytest.fixture
def parser() -> CitationParser:
    """Provides a fresh instance of CitationParser for each test."""
    return CitationParser()


def test_basic_and_coauthor_formats(parser: CitationParser) -> None:
    """Test standard Author, Author and Author, and Author et al."""
    text = "Hovius (1997), Parker and Smith (2011), and Larsen et al. (2012)."
    res = parser.extract_all(text)
    authors = [r["first_authors_txt"] for r in res]

    assert "Hovius" in authors
    assert "Parker and Smith" in authors
    assert "Larsen et al." in authors


def test_multiple_years_narrative(parser: CitationParser) -> None:
    """Verify: Author (Year1a, Year2b) -> Two distinct results with suffixes."""
    text = "Croissant et al. (2017a, 2019b) found specific patterns."
    res = parser.extract_all(text)

    assert len(res) == 2
    assert res[0]["year_and_suffix"] == "2017a"
    assert res[1]["year_and_suffix"] == "2019b"


@pytest.mark.parametrize(
    "text, expected_author",
    [
        ("L'étude de Dupont et Dupond (1945).", "Dupont et Dupond"),  # French 'et'
        ("J.S. Bach (1720) and (S.J-P. Lénard et al., 2024).", "J.S. Bach"),
        ("J.S. Bach (1720) and (S.J-P. Lénard et al., 2024).", "S.J-P. Lénard et al."),
        (
            "Van Der Beek (2026), van der Beek (2026), and De Castro (2010).",
            "Van Der Beek",
        ),
        ("Lyon-Caen and Molnar (1985) and Lénard (2020).", "Lyon-Caen and Molnar"),
        ("Lyon-Caen and Molnar (1985) and Lénard (2020).", "Lénard"),
        ("S.J-P. Lénard et al. (2020) demonstrated this.", "S.J-P. Lénard et al."),
    ],
)
def test_complex_names_and_particles(
    parser: CitationParser, text: str, expected_author: str
) -> None:
    """Verify handling of initials, particles, and accented/hyphenated names."""
    res = parser.extract_all(text)
    authors = [r["first_authors_txt"] for r in res]
    assert expected_author in authors


def test_nested_and_parenthetical_blocks(parser: CitationParser) -> None:
    """Test semicolon-separated groups and text inside double parentheses."""
    text = "((Larsen and Montgomery, 2012)). See also (Smith, 2003; Brown, 2005)."
    res = parser.extract_all(text)
    authors = [r["first_authors_txt"] for r in res]

    assert len(res) == 3
    assert "Larsen and Montgomery" in authors
    assert "Smith" in authors
    assert "Brown" in authors


def test_blacklist_and_noise(parser: CitationParser) -> None:
    """Ensure common labels (Fig. or Table) are ignored while similar names are kept."""
    text = "(Fig. 5; Hovius, 1997). Figueroa (2020) is not Fig."
    res = parser.extract_all(text)
    authors = [r["first_authors_txt"] for r in res]

    assert "Hovius" in authors
    assert "Figueroa" in authors
    assert "Fig." not in authors


def test_unicode_and_french_coordinators(parser: CitationParser) -> None:
    """Test names with Unicode dashes and French coordinators."""
    # Using Unicode hyphen (U+2010) in Lyon‐Caen
    text = "Work by Lyon‐Caen and Molnar (1985) and Lyon‐Caen et Molnar (1985)."
    res = parser.extract_all(text)

    assert len(res) == 2
    assert res[0]["first_authors_txt"] == "Lyon‐Caen and Molnar"
    assert res[1]["first_authors_txt"] == "Lyon‐Caen et Molnar"


@pytest.mark.parametrize(
    "text",
    [
        "This was resolved recently (2020).",
        "Occurred (in 2021).",
        "When this happened (August 31, 2020).",
        (
            "Bernard, T., G., Lague, D., and Philippe Steer, P. (2021). "
            "Beyond 2D Landslide Inventories. Earth Surface Dynamics 9 (4), 1013–44."
        ),
    ],
)
def test_exclusions(parser: CitationParser, text: str) -> None:
    """Ensure standalone years, dates, and full bibliography references are NOT
    captured."""
    res = parser.extract_all(text)
    assert len(res) == 0
