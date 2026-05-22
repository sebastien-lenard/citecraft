import pytest

from manuscript_reference_lister.parsers import HtmlCleaner
from manuscript_reference_lister.utils.config import create_config


@pytest.mark.parametrize(
    "raw_input, expected_output",
    [
        # =====================================================================
        # CASES WITH NEWLINES, Standard HTML collapsing behavior: \n + spaces -> 1 space
        # =====================================================================
        # Real-world Ref 2: CO2 Plumes (Newlines become standard spaces surrounding the
        # tag)
        (
            "Tracking CO\n          <sub>2</sub>\n          Plumes in Clay‐Rich Rock",
            "Tracking CO <sub>2</sub> Plumes in Clay‐Rich Rock",
        ),
        # Real-world Ref 3: Kaikōura earthquake case: Discarded <i> leaves spaces behind
        (
            "Complex multifault rupture during the 2016\n            <i>M</i>\n      "
            "      <sub>w</sub>\n            7.8 Kaikōura",
            "Complex multifault rupture during the 2016 M <sub>w</sub> 7.8 Kaikōura",
        ),
        # Real-world Specific Ref: RNA / Protein m6A
        (
            "Single-base mapping of m\n                    <sup>6</sup>\n           "
            "         A by an antibody-independent method.",
            "Single-base mapping of m <sup>6</sup> A by an antibody-independent "
            "method.",
        ),
        # Former Ref 2: Drosophila organism with \n pollution
        (
            "Two Dobzhansky-Muller Genes Interact to Cause Hybrid Lethality in\n"
            "                    <i>Drosophila</i>. Science",
            "Two Dobzhansky-Muller Genes Interact to Cause Hybrid Lethality in "
            "Drosophila. Science",
        ),
        # Former Ref 3 revised: Space normalization around exponents
        (
            "Ocean\n"
            "                    <sup>10</sup>\n"
            "                    Be(cosmogenic)/\n"
            "                    <sup>9</sup>\n"
            "                    Be as denudation rate proxy.",
            "Ocean <sup>10</sup> Be(cosmogenic)/ <sup>9</sup> Be as denudation rate "
            "proxy.",
        ),
        # =====================================================================
        # CASES WITHOUT NEWLINES (Strict preservation of standard spaces)
        # =====================================================================
        # Real-world Ref 1: Space preserved after closing tag
        (
            "Townsend, J. P. (2020). Liquid‐Vapor Coexistence and Critical Point of "
            "Mg<sub>2</sub>SiO<sub>4</sub> From Ab Initio Simulations.",
            "Townsend, J. P. (2020). Liquid‐Vapor Coexistence and Critical Point of "
            "Mg<sub>2</sub>SiO<sub>4</sub> From Ab Initio Simulations.",
        ),
        # Real-world Ref 4: Space preserved before magnitude value
        (
            "Volume Characteristics of Landslides Triggered by the M<sub>W</sub> 7.8 "
            "2016 Kaikōura Earthquake",
            "Volume Characteristics of Landslides Triggered by the M<sub>W</sub> 7.8 "
            "2016 Kaikōura Earthquake",
        ),
        # Former Ref 4: Electron configuration remains unmodified
        (
            "Experimental and Theoretical Comparison of the Metallophilicity between "
            "d<sup>10</sup>–d<sup>10</sup>Au<sup>I</sup>–Hg<sup>II</sup>and d<sup>8"
            "</sup>–d<sup>10</sup>Au<sup>III</sup>–Hg<sup>II</sup>Interactions.",
            "Experimental and Theoretical Comparison of the Metallophilicity between "
            "d<sup>10</sup>–d<sup>10</sup>Au<sup>I</sup>–Hg<sup>II</sup>and d<sup>8"
            "</sup>–d<sup>10</sup>Au<sup>III</sup>–Hg<sup>II</sup>Interactions.",
        ),
        # Former Ref 5: Scientific units and words like "to" remain intact
        (
            " Helium Low Gas Flow Measurements in the Range 10<sup>−13</sup> to "
            "10<sup>−11</sup> mol/s (10<sup>−9</sup> to 10<sup>−7</sup> cm<sup>3</sup>"
            "/s).",
            "Helium Low Gas Flow Measurements in the Range 10<sup>−13</sup> to "
            "10<sup>−11</sup> mol/s (10<sup>−9</sup> to 10<sup>−7</sup> cm<sup>3</sup>"
            "/s).",
        ),
        # Standard chemical formulas without \n
        (
            "H<sub>2</sub>O and Na<sup>+</sup> ions or SO<sub>4</sub><sup>2-</sup>",
            "H<sub>2</sub>O and Na<sup>+</sup> ions or SO<sub>4</sub><sup>2-</sup>",
        ),
        # =====================================================================
        # ENTITIES AND SAFETY
        # =====================================================================
        ("Lénárd &amp; Müller &quot;v/s&quot; Ørsted", 'Lénárd & Müller "v/s" Ørsted'),
        ("", ""),
    ],
)
def test_clean_to_plain_text(raw_input: str, expected_output: str) -> None:
    """Verify that HTML cleanup correctly normalizes text based on standard whitespace
    collapsing."""
    cleaner = HtmlCleaner()
    assert cleaner.clean_to_plain_text(raw_input) == expected_output


def test_html_cleaner_uses_injected_config() -> None:
    """Verify that HtmlCleaner respects custom tags provided via AppConfig."""
    test_config = create_config()
    test_config.preserved_html_tags = {"custom-sup"}
    test_config.discarded_html_tags = {"custom-i"}

    cleaner = HtmlCleaner(config=test_config)

    raw_input = (
        "<custom-sup>10</custom-sup> <custom-i>Text</custom-i> <sub>Skipped</sub>"
    )

    expected = "<custom-sup>10</custom-sup> Text Skipped"

    assert cleaner.clean_to_plain_text(raw_input) == expected
