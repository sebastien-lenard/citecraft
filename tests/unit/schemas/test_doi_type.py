import pytest

from citecraft.schemas import check_standalone_doi


@pytest.mark.parametrize(
    "doi",
    [
        "10.1029/2009jf001321",
        "10.1080/00288306.2021.1975777",
        "10.1016/0169-555x(92)90057-u",
        "10.1038/ngeo3005",
        "10.1016/j.geomorph.2019.04.017",
        "10.1130/0091-7613(2000)28",
        "10.1038/s41467-022-32853-5",
        "10.1016/0169-?555x(92)90057-u",
        "10.1007/s10346-020-01439-x",
        "10.1038/ngeo3!005",
        "10.1130/0091-7613(1997)025<0231:sffamb>2.3.co;2",
        "10.1002/(SICI)1521-3951(199911)216:1<135::AID-PSSB135>3.0.CO;2-#",
        "10.1130/0091-7613(1997)025<0231:sffamb>#%2.3.co;2",
        "10.1130/0091-7613(1997)025<?&$^@\0231:sffamb>#%2.3.co;2",
        "10.1002/9780470015902.a0029584/v2",
    ],
)
def test_check_standalone_doi_valid(doi: str) -> None:
    """Ensure that valid DOI values pass validation without warnings."""
    assert check_standalone_doi(doi) is True


@pytest.mark.parametrize(
    "invalid_doi",
    [
        "10a.1029/2009jf001321",
        "10.1080 00288306.2021.1975777",
        "410.1016/j.geomorph.2019.04.017",
        "10.1016/j.geomorph.2019 .04.017",
        "10.1016/j.geomorph.2019.04.017.",
    ],
)
def test_check_standalone_doi_invalid(invalid_doi: str) -> None:
    """Ensure that invalid DOI values does not pass validation without warnings."""
    assert check_standalone_doi(invalid_doi) is False
