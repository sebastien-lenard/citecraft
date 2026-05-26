import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from manuscript_reference_lister.repositories import StyleRepository


@pytest.fixture
def valid_csl_content() -> str:
    """Provides a minimal valid CSL layout string."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://purl.org/net/xbiblio/csl"\n'
        '  class="in-text" version="1.0">\n'
        "  <info><title>Mock Style</title></info>\n"
        "</style>"
    )


def test_init_fallback_rules() -> None:
    """Verify init rules of favored_style."""
    # No argument
    repo_default = StyleRepository()
    assert repo_default.favored_style == "apa"

    # Only favored_style
    repo_style = StyleRepository(favored_style="harvard")
    assert repo_style.favored_style == "harvard"

    # Only favored_journal_title
    repo_journal = StyleRepository(favored_journal_title="Nature")
    assert repo_journal.favored_style is None

    # Two provided
    repo_conflict = StyleRepository(favored_journal_title="Nature", favored_style="apa")
    assert repo_conflict.favored_style is None


def test_fetch_style_metadata_success(valid_csl_content: str) -> None:
    """Verify CSL content is successfully downloaded and stored."""
    repo = StyleRepository(favored_style="apa")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = valid_csl_content

    with patch.object(
        repo.http_client_wrapper, "get", return_value=mock_response
    ) as mock_get:
        repo.fetch_style_metadata()
        assert repo.csl_content == valid_csl_content
        assert mock_get.call_count == 1


def test_fetch_style_metadata_not_found() -> None:
    """Verify fallback when CSL endpoint returns a 404 error."""
    repo = StyleRepository(favored_style="invalid-style")
    mock_request = httpx.Request("GET", "https://raw.githubusercontent.com/invalid")
    mock_response = httpx.Response(status_code=404, request=mock_request)

    error = httpx.HTTPStatusError(
        message="404 Not Found", request=mock_request, response=mock_response
    )

    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        repo.fetch_style_metadata()
        assert repo.csl_content is None
        assert repo.favored_style_is_valid is None


def test_fetch_style_metadata_resolves_journal_late() -> None:
    """Verify late solving of style by fetch_style_metadata."""
    repo = StyleRepository(favored_journal_title="Nature")

    with (
        patch.object(repo, "get_style", return_value="nature") as mock_get_style,
        patch.object(repo.http_client_wrapper, "get") as mock_get_http,
    ):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.text = "mock-csl-payload"
        mock_get_http.return_value = mock_res

        repo.fetch_style_metadata()

        mock_get_style.assert_called_once_with("Nature")
        assert repo.favored_style == "nature"
        assert repo.csl_content == "mock-csl-payload"


def test_fetch_style_metadata_abort_when_no_style_resolved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify clean interruption if no style found."""
    repo = StyleRepository(favored_journal_title="Unknown Journal")

    with (
        patch.object(repo, "get_style", return_value=None),
        caplog.at_level(logging.WARNING),
    ):
        repo.fetch_style_metadata()

        assert repo.csl_content is None
        assert any(
            "No favored style determined" in record.message for record in caplog.records
        )


def test_get_style_success_independent() -> None:
    """Verify that looking up a non-dependent journal directly returns its slug."""
    repo = StyleRepository()
    mock_index = [{"title": "Nature", "name": "nature", "dependent": False}]

    mock_res = MagicMock()
    mock_res.json.return_value = mock_index

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_res):
        style = repo.get_style("Nature")
        assert style == "nature"


def test_get_style_success_dependent() -> None:
    """Verify independent parent style resolution when a journal is dependent."""
    repo = StyleRepository()
    mock_index = [
        {
            "title": "Journal of Geophysical Research: Solid Earth",
            "name": "jgr-solid-earth",
            "dependent": True,
        }
    ]

    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    # Minimal XML mimicking a dependent style pointing to AGU parent style
    mock_xml_content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://citationstyles.org/ns/" version="1.0">\n'
        "  <info>\n"
        '    <link rel="independent-parent" '
        'href="http://www.zotero.org/styles/american-geophysical-union"/>\n'
        "  </info>\n"
        "</style>"
    )
    mock_res_xml = MagicMock()
    mock_res_xml.text = mock_xml_content
    mock_res_xml.content = mock_xml_content.encode("utf-8")

    # Sequence mock: first call gets index, second gets XML payload
    with patch.object(
        repo.http_client_wrapper, "get", side_effect=[mock_res_index, mock_res_xml]
    ):
        style = repo.get_style("Geophysical Research: Solid Earth")
        assert style == "american-geophysical-union"


def test_get_style_bubbles_http_error() -> None:
    """Vérifie que get_style laisse remonter les crashs HTTP de l'index Zotero."""
    repo = StyleRepository()
    mock_request = httpx.Request("GET", "https://example.com")
    error = httpx.HTTPStatusError(
        "500 Internal Server Error", request=mock_request, response=httpx.Response(500)
    )

    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        with pytest.raises(httpx.HTTPStatusError):
            repo.get_style("Nature")


def test_get_style_bubbles_json_decode_error() -> None:
    """Vérifie que get_style laisse remonter les erreurs de décodage JSON de l'index."""
    repo = StyleRepository()
    mock_res = MagicMock()
    mock_res.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_res):
        with pytest.raises(ValueError, match="Expecting value"):
            repo.get_style("Nature")


def test_get_style_malformed_json_raises_type_error() -> None:
    """Ensure a TypeError is raised with log diagnostics if JSON root is not a list."""
    repo = StyleRepository()
    mock_res = MagicMock()
    mock_res.json.return_value = {"error": "not a list"}  # Invalid structure type

    with patch.object(repo.http_client_wrapper, "get", return_value=mock_res):
        with pytest.raises(TypeError):
            repo.get_style("Any Journal")


def test_resolve_parent_missing_xml_namespace() -> None:
    """Verify exception raised if CSL XML CSL has no namespace."""
    repo = StyleRepository()
    mock_index = [{"title": "Dependent J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    # XML without xmlns attribute
    malformed_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style version="1.0">\n'
        '  <info><link rel="independent-parent" href="http://example.com/parent"/></info>\n'
        "</style>"
    )
    mock_res_xml = MagicMock()
    mock_res_xml.content = malformed_xml.encode("utf-8")

    with patch.object(
        repo.http_client_wrapper, "get", side_effect=[mock_res_index, mock_res_xml]
    ):
        with pytest.raises(ValueError, match="does not define a namespace"):
            repo.get_style("Dependent J")


def test_resolve_parent_empty_parent_href(caplog: pytest.LogCaptureFixture) -> None:
    """Verifies behavior when parent tag exists but empty href."""
    repo = StyleRepository()
    mock_index = [{"title": "Dependent J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    # XML having empty href
    xml_empty_href = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://citationstyles.org/ns/" version="1.0">\n'
        "  <info>\n"
        '    <link rel="independent-parent" href=""/>\n'
        "  </info>\n"
        "</style>"
    )
    mock_res_xml = MagicMock()
    mock_res_xml.content = xml_empty_href.encode("utf-8")

    with (
        patch.object(
            repo.http_client_wrapper, "get", side_effect=[mock_res_index, mock_res_xml]
        ),
        caplog.at_level(logging.WARNING),
    ):
        result = repo.get_style("Dependent J")
        assert result is None
        assert any(
            "No 'independent-parent' link found" in record.message
            for record in caplog.records
        )


def test_validate_favored_style_success(valid_csl_content: str) -> None:
    """Verify validation passes when XML boundaries are matching specifications."""
    repo = StyleRepository(favored_style="apa")
    repo.csl_content = valid_csl_content

    repo.validate_favored_style()
    assert repo.favored_style_is_valid is True


def test_validate_favored_style_structure_failure() -> None:
    """Verify validation fails when structural XML markers are invalid or missing."""
    repo = StyleRepository(favored_style="apa")
    repo.csl_content = "<style>Invalid Header structure</style>"

    repo.validate_favored_style()
    assert repo.favored_style_is_valid is False
