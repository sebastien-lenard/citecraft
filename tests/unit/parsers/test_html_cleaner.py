import pytest

from manuscript_reference_lister.parsers import HtmlCleaner
from manuscript_reference_lister.utils import AppConfig


@pytest.mark.parametrize(
    "raw_input, expected_output",
    [
        # =====================================================================
        # CASES WITH NEWLINES, Standard HTML collapsing behavior: \n + spaces -> 1 space
        # =====================================================================
        (
            "Tracking CO\n          <sub>2</sub>\n          Plumes in Clay‐Rich Rock",
            "Tracking CO <sub>2</sub> Plumes in Clay‐Rich Rock",
        ),
        (
            "Complex multifault rupture during the 2016\n            <i>M</i>\n      "
            "      <sub>w</sub>\n            7.8 Kaikōura",
            "Complex multifault rupture during the 2016 M <sub>w</sub> 7.8 Kaikōura",
        ),
        (
            "Single-base mapping of m\n                    <sup>6</sup>\n           "
            "         A by an antibody-independent method.",
            "Single-base mapping of m <sup>6</sup> A by an antibody-independent"
            " method.",
        ),
        (
            "Two Dobzhansky-Muller Genes Interact to Cause Hybrid Lethality in\n"
            "                    <i>Drosophila</i>. Science",
            "Two Dobzhansky-Muller Genes Interact to Cause Hybrid Lethality in "
            "Drosophila. Science",
        ),
        (
            "Ocean\n"
            "                    <sup>10</sup>\n"
            "                    Be(cosmogenic)/\n"
            "                    <sup>9</sup>\n"
            "                    Be as denudation rate proxy.",
            "Ocean <sup>10</sup> Be(cosmogenic)/ <sup>9</sup> Be as denudation rate"
            " proxy.",
        ),
        # =====================================================================
        # CASES WITHOUT NEWLINES (Strict preservation of standard spaces)
        # =====================================================================
        (
            "Townsend, J. P. (2020). Liquid‐Vapor Coexistence and Critical Point of "
            "Mg<sub>2</sub>SiO<sub>4</sub> From Ab Initio Simulations.",
            "Townsend, J. P. (2020). Liquid‐Vapor Coexistence and Critical Point of "
            "Mg<sub>2</sub>SiO<sub>4</sub> From Ab Initio Simulations.",
        ),
        (
            "Volume Characteristics of Landslides Triggered by the M<sub>W</sub> 7.8 "
            "2016 Kaikōura Earthquake",
            "Volume Characteristics of Landslides Triggered by the M<sub>W</sub> 7.8 "
            "2016 Kaikōura Earthquake",
        ),
        (
            "Experimental and Theoretical Comparison of the Metallophilicity between "
            "d<sup>10</sup>–d<sup>10</sup>Au<sup>I</sup>–Hg<sup>II</sup>and d<sup>8"
            "</sup>–d<sup>10</sup>Au<sup>III</sup>–Hg<sup>II</sup>Interactions.",
            "Experimental and Theoretical Comparison of the Metallophilicity between "
            "d<sup>10</sup>–d<sup>10</sup>Au<sup>I</sup>–Hg<sup>II</sup>and d<sup>8"
            "</sup>–d<sup>10</sup>Au<sup>III</sup>–Hg<sup>II</sup>Interactions.",
        ),
        (
            " Helium Low Gas Flow Measurements in the Range 10<sup>−13</sup> to "
            "10<sup>−11</sup> mol/s (10<sup>−9</sup> to 10<sup>−7</sup> cm<sup>3</sup>"
            "/s).",
            "Helium Low Gas Flow Measurements in the Range 10<sup>−13</sup> to "
            "10<sup>−11</sup> mol/s (10<sup>−9</sup> to 10<sup>−7</sup> cm<sup>3</sup>"
            "/s).",
        ),
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
    """Verify HTML cleanup normalizes texts based on whitespace collapsing rules."""
    cleaner = HtmlCleaner()
    assert cleaner.clean_to_plain_text(raw_input) == expected_output


def test_html_cleaner_uses_injected_config(test_config: AppConfig) -> None:
    """Verify that HtmlCleaner respects custom tags configured via AppConfig."""
    test_config.preserved_html_tags = {"custom-sup"}
    test_config.discarded_html_tags = {"custom-i"}
    cleaner = HtmlCleaner(config=test_config)
    raw_input = (
        "<custom-sup>10</custom-sup> <custom-i>Text</custom-i> <sub>Skipped</sub>"
    )

    expected = "<custom-sup>10</custom-sup> Text Skipped"

    assert cleaner.clean_to_plain_text(raw_input) == expected
