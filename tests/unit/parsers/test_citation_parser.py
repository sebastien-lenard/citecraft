# tests/unit/parsers/test_citation_parser.py
import pytest

from citecraft.parsers import CitationParser


@pytest.fixture
def parser() -> CitationParser:
    """Provide a fresh CitationParser instance for isolated testing."""
    return CitationParser()


@pytest.mark.parametrize(
    "text, expected_authors",
    [
        # Coauthor formats
        (
            "Hovius (1997), Parker and Smith (2011), and Larsen et al. (2012).",
            ["Hovius", "Parker and Smith", "Larsen et al."],
        ),
        # Nested and parenthetical blocks
        (
            "((Larsen and Montgomery, 2012)). See also (Smith, 2003; Brown, 2005).",
            ["Larsen and Montgomery", "Smith", "Brown"],
        ),
        # Blacklist and noise handling (ignoring 'Fig.' but keeping 'Figueroa')
        (
            "(Fig. 5; Hovius, 1997). Figueroa (2020) is not Fig.",
            ["Hovius", "Figueroa"],
        ),
        # Accented and complex initials/particles
        (
            "L'étude de Dupont et Dupond (1945).",
            ["Dupont et Dupond"],
        ),
        (
            "J.S. Bach (1720) and (S.J-P. Lénard et al., 2024).",
            ["J.S. Bach", "S.J-P. Lénard et al."],
        ),
        (
            "Van Der Beek (2026), van der Beek (2026), and De Castro (2010).",
            ["Van Der Beek", "van der Beek", "De Castro"],
        ),
        (
            "Lyon-Caen and Molnar (1985) and Lénard (2020).",
            ["Lyon-Caen and Molnar", "Lénard"],
        ),
        (
            "S.J-P. Lénard et al. (2020) demonstrated this.",
            ["S.J-P. Lénard et al."],
        ),
        # Unicode hyphens and language coordinators
        (
            "Work by Lyon‐Caen and Molnar (1985) and Lyon‐Caen et Molnar (1985).",  # noqa: RUF001
            ["Lyon‐Caen and Molnar", "Lyon‐Caen et Molnar"],  # noqa: RUF001
        ),
    ],
)
def test_citation_parser_extractions(
    parser: CitationParser, text: str, expected_authors: list[str],
) -> None:
    """Verify successful citation parsings across diverse formatting combinations."""
    res = parser.extract_all(text)
    authors = [r.first_authors_txt for r in res]

    assert len(res) == len(expected_authors)
    for expected in expected_authors:
        assert expected in authors


def test_multiple_years_narrative(parser: CitationParser) -> None:
    """Verify multiple suffix years are parsed as distinct citation structures."""
    text = "Croissant et al. (2017a, 2019b) found specific patterns."
    res = parser.extract_all(text)

    assert len(res) == 2
    assert res[0].year_and_suffix == "2017a"
    assert res[1].year_and_suffix == "2019b"


@pytest.mark.parametrize(
    "text",
    [
        "This was resolved recently (2020).",
        "Occurred (in 2021).",
        "When this happened (August 31, 2020).",
        (
            "Bernard, T., G., Lague, D., and Philippe Steer, P. (2021). "
            "Beyond 2D Landslide Inventories. Earth Surface Dynamics 9 (4), 1013–44."  # noqa: RUF001
        ),
    ],
)
def test_exclusions(parser: CitationParser, text: str) -> None:
    """Verify standalone years, isolated dates, and bibliography items are skipped."""
    res = parser.extract_all(text)
    assert len(res) == 0
