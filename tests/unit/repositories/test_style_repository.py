# tests/unit/repositories/test_style_repository.py
"""Unit tests verifying CSL lookup inheritance mechanics and layout validation."""

import logging
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import httpx
import pytest
from defusedxml import ElementTree

from citecraft.repositories import StyleRepository
from citecraft.utils import AppConfig


@pytest.fixture
def valid_csl_content() -> str:
    """Provide a minimal valid CSL layout string."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://purl.org/net/xbiblio/csl"\n'
        '  class="in-text" version="1.0">\n'
        "  <info><title>Mock Style</title></info>\n"
        "</style>"
    )


@pytest.mark.parametrize(
    ("favored_style", "favored_journal", "expected_favored_style"),
    [
        (None, None, "apa"),
        ("harvard", None, "harvard"),
        (None, "Nature", None),
        ("apa", "Nature", None),
    ],
)
def test_init_fallback_rules(
    test_config: AppConfig,
    favored_style: str | None,
    favored_journal: str | None,
    expected_favored_style: str | None,
) -> None:
    """Verify initialization rules and precedence of favored_style options."""
    repo = StyleRepository(
        favored_style=favored_style,
        favored_journal_title=favored_journal,
        config=test_config,
    )
    assert repo.favored_style == expected_favored_style


def test_fetch_style_metadata_success(
    test_config: AppConfig,
    valid_csl_content: str,
) -> None:
    """Verify CSL content is successfully downloaded and stored."""
    repo = StyleRepository(favored_style="apa", config=test_config)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = valid_csl_content

    with patch.object(
        repo.http_client_wrapper,
        "get",
        return_value=(mock_response, None),
    ) as mock_get:
        repo.fetch_style_metadata()

        assert repo.csl_content == valid_csl_content
        assert mock_get.call_count == 1


def test_fetch_style_metadata_not_found(test_config: AppConfig) -> None:
    """Verify fallback when CSL endpoint returns a 404 error."""
    repo = StyleRepository(favored_style="invalid-style", config=test_config)
    mock_request = httpx.Request("GET", "https://raw.githubusercontent.com/invalid")
    mock_response = httpx.Response(status_code=404, request=mock_request)
    error = httpx.HTTPStatusError(
        message="404 Not Found",
        request=mock_request,
        response=mock_response,
    )

    with patch.object(repo.http_client_wrapper, "get", side_effect=error):
        repo.fetch_style_metadata()

        assert repo.csl_content is None
        assert repo.favored_style_is_valid is None


def test_fetch_style_metadata_resolves_journal_late(test_config: AppConfig) -> None:
    """Verify late solving of style by fetch_style_metadata."""
    repo = StyleRepository(favored_journal_title="Nature", config=test_config)

    with (
        patch.object(repo, "get_style", return_value="nature") as mock_get_style,
        patch.object(repo.http_client_wrapper, "get") as mock_get_http,
    ):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.text = "mock-csl-payload"
        mock_get_http.return_value = (mock_res, None)

        repo.fetch_style_metadata()

        mock_get_style.assert_called_once_with("Nature")
        assert repo.favored_style == "nature"
        assert repo.csl_content == "mock-csl-payload"


def test_fetch_style_metadata_abort_when_no_style_resolved(
    test_config: AppConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify clean interruption if no style can be resolved."""
    repo = StyleRepository(favored_journal_title="Unknown Journal", config=test_config)

    with (
        patch.object(repo, "get_style", return_value=None),
        caplog.at_level(logging.WARNING),
    ):
        repo.fetch_style_metadata()

        assert repo.csl_content is None
        assert any(
            "No favored style determined" in record.message for record in caplog.records
        )


def test_get_style_success_independent(test_config: AppConfig) -> None:
    """Verify that looking up a non-dependent journal directly returns its slug."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Nature", "name": "nature", "dependent": False}]
    mock_res = MagicMock()
    mock_res.json.return_value = mock_index

    with patch.object(repo.http_client_wrapper, "get", return_value=(mock_res, None)):
        style = repo.get_style("Nature")
        assert style == "nature"


def test_get_style_success_dependent(test_config: AppConfig) -> None:
    """Verify independent parent style resolution when a journal is dependent."""
    repo = StyleRepository(config=test_config)
    mock_index = [
        {
            "title": "Journal of Geophysical Research: Solid Earth",
            "name": "jgr-solid-earth",
            "dependent": True,
        },
    ]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

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
    mock_res_xml.content = mock_xml_content.encode("utf-8")

    with patch.object(
        repo.http_client_wrapper,
        "get",
        side_effect=[(mock_res_index, None), (mock_res_xml, None)],
    ):
        style = repo.get_style("Geophysical Research: Solid Earth")
        assert style == "american-geophysical-union"


@pytest.mark.parametrize(
    ("config_mock_callable", "expected_exception", "expected_match"),
    [
        # Case A: Zotero API status crashes propagate up
        (
            lambda m: m.configure_mock(
                side_effect=httpx.HTTPStatusError(
                    "500 Internal Error",
                    request=httpx.Request("GET", "https://example.com"),
                    response=httpx.Response(500),
                ),
            ),
            httpx.HTTPStatusError,
            "500 Internal Error",
        ),
        # Case B: Index decoding exceptions propagate up
        (
            lambda m: m.configure_mock(
                return_value=(
                    MagicMock(
                        json=MagicMock(side_effect=ValueError("Expecting value")),
                    ),
                    None,
                ),
            ),
            ValueError,
            "Expecting value",
        ),
        # Case C: Non-list formats raise TypeError
        (
            lambda m: m.configure_mock(
                return_value=(
                    MagicMock(json=MagicMock(return_value={"error": "not a list"})),
                    None,
                ),
            ),
            TypeError,
            None,
        ),
    ],
)
def test_get_style_failures_propagate(
    test_config: AppConfig,
    config_mock_callable: Callable[[MagicMock], None],
    expected_exception: type[Exception],
    expected_match: str | None,
) -> None:
    """Verify that network and parsing failures in style lookups bubble up cleanly."""
    repo = StyleRepository(config=test_config)

    with patch.object(repo.http_client_wrapper, "get") as mock_get:
        config_mock_callable(mock_get)

        with pytest.raises(expected_exception, match=expected_match):
            repo.get_style("Nature")


def test_resolve_parent_missing_xml_namespace(test_config: AppConfig) -> None:
    """Verify exception raised if CSL XML has no namespace defined."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dependent J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    malformed_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style version="1.0">\n'
        '  <info><link rel="independent-parent" href="http://example.com"/></info>\n'
        "</style>"
    )
    mock_res_xml = MagicMock()
    mock_res_xml.content = malformed_xml.encode("utf-8")

    with (
        patch.object(
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, None), (mock_res_xml, None)],
        ),
        pytest.raises(ValueError, match="does not define a namespace"),
    ):
        repo.get_style("Dependent J")


def test_resolve_parent_empty_parent_href(
    test_config: AppConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify clean fallback warning when parent href is empty."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dependent J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

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
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, None), (mock_res_xml, None)],
        ),
        caplog.at_level(logging.WARNING),
    ):
        result = repo.get_style("Dependent J")

        assert result is None
        assert any(
            "No 'independent-parent' link found" in record.message
            for record in caplog.records
        )


@pytest.mark.parametrize(
    ("csl_payload", "expected_validity"),
    [
        # Case A: Valid CSL XML payload
        (
            (
                '<?xml version="1.0" encoding="utf-8"?>\n<style '
                'xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">'
                "<info><title>Mock</title></info></style>"
            ),
            True,
        ),
        # Case B: Malformed XML root structures
        (
            "<style>Invalid Header structure</style>",
            False,
        ),
    ],
)
def test_validate_favored_style_scenarios(
    test_config: AppConfig,
    csl_payload: str,
    expected_validity: bool,
) -> None:
    """Verify structural XML validation flags matching specifications."""
    repo = StyleRepository(favored_style="apa", config=test_config)
    repo.csl_content = csl_payload

    repo.validate_favored_style()

    assert repo.favored_style_is_valid is expected_validity


# =============================================================================
# COV TESTS: SPECIFIC IF/ELSE AND FALLBACK BRANCH COVERAGE
# =============================================================================


def test_fetch_style_metadata_response_none(test_config: AppConfig) -> None:
    """Cover L62 in fetch_style_metadata(): response is None."""
    repo = StyleRepository(favored_style="apa", config=test_config)
    with patch.object(repo.http_client_wrapper, "get", return_value=(None, 0)):
        repo.fetch_style_metadata()
        assert repo.csl_content is None


def test_fetch_style_metadata_raises_unexpected_http_error(
    test_config: AppConfig,
) -> None:
    """Cover L85 in fetch_style_metadata(): raise unexpected http status error."""
    repo = StyleRepository(favored_style="apa", config=test_config)
    mock_request = httpx.Request("GET", "https://raw.githubusercontent.com/invalid")
    mock_response = httpx.Response(status_code=500, request=mock_request)
    error = httpx.HTTPStatusError(
        "500 Server Error",
        request=mock_request,
        response=mock_response,
    )
    with (
        patch.object(repo.http_client_wrapper, "get", side_effect=error),
        pytest.raises(httpx.HTTPStatusError),
    ):
        repo.fetch_style_metadata()


def test_get_style_empty_title_returns_none(test_config: AppConfig) -> None:
    """Cover L91 in get_style(): empty journal_title returns None."""
    repo = StyleRepository(config=test_config)
    assert repo.get_style("") is None


def test_get_style_response_none_raises_value_error(
    test_config: AppConfig,
) -> None:
    """Cover L101 in get_style(): response is None raises ValueError."""
    repo = StyleRepository(config=test_config)
    with (
        patch.object(repo.http_client_wrapper, "get", return_value=(None, 0)),
        pytest.raises(ValueError, match="Empty index response received"),
    ):
        repo.get_style("Nature")


def test_get_style_no_match_returns_none(test_config: AppConfig) -> None:
    """Cover L134 in get_style(): fuzzy match fails and returns None."""
    repo = StyleRepository(config=test_config)
    mock_res = MagicMock()
    mock_res.json.return_value = [{"title": "Nature", "name": "nature"}]
    with patch.object(repo.http_client_wrapper, "get", return_value=(mock_res, 0)):
        assert repo.get_style("Nonexistent Journal") is None


def test_fuzzy_match_skips_non_dict_elements(test_config: AppConfig) -> None:
    """Cover L149 in _fuzzy_match_style(): skip if style is not a dict."""
    repo = StyleRepository(config=test_config)
    mock_res = MagicMock()
    mock_res.json.return_value = [
        "corrupted_list_element",
        {"title": "Nature", "name": "nature"},
    ]
    with patch.object(repo.http_client_wrapper, "get", return_value=(mock_res, 0)):
        assert repo.get_style("Nature") == "nature"


def test_fuzzy_match_skips_incomplete_elements(test_config: AppConfig) -> None:
    """Cover L154 in _fuzzy_match_style(): skip if title or style_name is empty."""
    repo = StyleRepository(config=test_config)
    mock_res = MagicMock()
    mock_res.json.return_value = [
        {"title": "", "name": "nature"},
        {"title": "Nature", "name": ""},
        {"title": "Nature", "name": "nature"},
    ]
    with patch.object(repo.http_client_wrapper, "get", return_value=(mock_res, 0)):
        assert repo.get_style("Nature") == "nature"


def test_resolve_parent_response_none_raises_value_error(
    test_config: AppConfig,
) -> None:
    """Cover L184 in _resolve_independent_parent(): response is None."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dep J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index
    with (
        patch.object(
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, 0), (None, 0)],
        ),
        pytest.raises(ValueError, match="No response payload returned"),
    ):
        repo.get_style("Dep J")


def test_resolve_parent_status_error_raises(test_config: AppConfig) -> None:
    """Cover L193 in _resolve_independent_parent(): httpx.HTTPStatusError raises."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dep J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    mock_req = httpx.Request("GET", "https://raw.githubusercontent.com/invalid")
    mock_res_xml = httpx.Response(status_code=500, request=mock_req)
    status_err = httpx.HTTPStatusError(
        "500 Server Error",
        request=mock_req,
        response=mock_res_xml,
    )

    with (
        patch.object(
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, 0), status_err],
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        repo.get_style("Dep J")


def test_resolve_parent_xml_parse_error_raises(test_config: AppConfig) -> None:
    """Cover L208 in _resolve_independent_parent(): ElementTree.ParseError raises."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dep J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    mock_res_xml = MagicMock()
    mock_res_xml.text = "corrupted xml formatting"
    mock_res_xml.content = b"corrupted xml formatting"

    with (
        patch.object(
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, 0), (mock_res_xml, 0)],
        ),
        pytest.raises(ElementTree.ParseError),
    ):
        repo.get_style("Dep J")


def test_resolve_parent_unrecognized_namespace_raises_value_error(
    test_config: AppConfig,
) -> None:
    """Cover L241 in _resolve_independent_parent(): unrecognized prefix namespace."""
    repo = StyleRepository(config=test_config)
    mock_index = [{"title": "Dep J", "name": "dep-j", "dependent": True}]
    mock_res_index = MagicMock()
    mock_res_index.json.return_value = mock_index

    unrecognized_ns_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<style xmlns="http://unrecognized.namespace.org/" version="1.0">\n'
        "  <info>\n"
        '    <link rel="independent-parent" href="http://example.com"/>\n'
        "  </info>\n"
        "</style>"
    )
    mock_res_xml = MagicMock()
    mock_res_xml.content = unrecognized_ns_xml.encode("utf-8")

    with (
        patch.object(
            repo.http_client_wrapper,
            "get",
            side_effect=[(mock_res_index, 0), (mock_res_xml, 0)],
        ),
        pytest.raises(ValueError, match="Unrecognized CSL namespace"),
    ):
        repo.get_style("Dep J")


def test_validate_favored_style_empty_content(test_config: AppConfig) -> None:
    """Cover L268 in validate_favored_style(): if not self.csl_content."""
    repo = StyleRepository(favored_style="apa", config=test_config)
    repo.csl_content = None
    repo.validate_favored_style()
    assert repo.favored_style_is_valid is False
