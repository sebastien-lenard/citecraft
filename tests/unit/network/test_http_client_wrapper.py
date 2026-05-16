from collections.abc import Generator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import TypeAdapter, networks

from manuscript_reference_lister.network.http_client_wrapper import HTTPClientWrapper


@pytest.fixture
def wrapper() -> Generator[HTTPClientWrapper, None, None]:
    """Provides an HTTPClientWrapper instance with low backoff and no initial delay for
    fast, deterministic testing.
    Note: We explicitly call wrapper.close() to free client resources.
    """
    client_wrapper = HTTPClientWrapper(
        email="test@example.com", max_retries=3, backoff_factor=0.1, delay=0.0
    )
    yield client_wrapper
    client_wrapper.close()


def test_get_success(wrapper: HTTPClientWrapper) -> None:
    """Verify that a successful request returns the response immediately."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "send", return_value=mock_response) as mock_get:
        response = wrapper.get("https://api.test.com")

        assert response == mock_response
        assert mock_get.call_count == 1


def test_get_retry_on_timeout(wrapper: HTTPClientWrapper) -> None:
    """Verify that the wrapper retries upon receiving a TransportError exception."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    # Simulate two failures followed by one success
    request_obj = httpx.Request("GET", "https://api.test.com")

    with (
        patch.object(wrapper.client, "get") as mock_get,
        patch("tenacity.nap.time.sleep") as mock_tenacity_sleep,
    ):
        mock_get.side_effect = [
            httpx.ReadTimeout("Slow connection", request=request_obj),
            httpx.ReadTimeout("Still slow", request=request_obj),
            mock_response,
        ]

        response = wrapper.get("https://api.test.com")

        assert response == mock_response
        assert mock_get.call_count == 3
        assert mock_tenacity_sleep.call_count == 2  # 2 sleeps for 3 retries


def test_get_retry_on_transient_http_errors(wrapper: HTTPClientWrapper) -> None:
    """Verify that transient HTTP errors (429, 503) trigger retries."""
    mock_response_ok = MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200

    request_obj = httpx.Request("GET", "https://api.test.com")

    mock_response_429 = MagicMock(spec=httpx.Response)
    mock_response_429.status_code = 429
    error_429 = httpx.HTTPStatusError(
        "Too Many Requests", request=request_obj, response=mock_response_429
    )

    mock_response_503 = MagicMock(spec=httpx.Response)
    mock_response_503.status_code = 503
    error_503 = httpx.HTTPStatusError(
        "Service Unavailable", request=request_obj, response=mock_response_503
    )

    with (
        patch.object(wrapper.client, "get") as mock_get,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_get.side_effect = [error_429, error_503, mock_response_ok]

        response = wrapper.get("https://api.test.com")

        assert response == mock_response_ok
        assert mock_get.call_count == 3


def test_get_max_retries_reached(wrapper: HTTPClientWrapper) -> None:
    """Verify the wrapper raises the last exception after max retries are exhausted."""
    request_obj = httpx.Request("GET", "https://api.test.com")

    with (
        patch.object(wrapper.client, "get") as mock_get,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_get.side_effect = httpx.ConnectError("Down", request=request_obj)

        with pytest.raises(httpx.ConnectError):
            wrapper.get("https://api.test.com")

        assert mock_get.call_count == 3


def test_get_fatal_http_error(wrapper: HTTPClientWrapper) -> None:
    """Verify that fatal HTTP errors (like 404) raise immediately without retry."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404

    request_obj = httpx.Request("GET", "https://api.test.com")
    error_404 = httpx.HTTPStatusError(
        "404 Not Found", request=request_obj, response=mock_response
    )

    with (
        patch.object(wrapper.client, "get", side_effect=error_404) as mock_get,
        patch("tenacity.nap.time.sleep") as mock_tenacity_sleep,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            wrapper.get("https://api.test.com")

        # Fatal errors should stop at the first attempt
        assert mock_get.call_count == 1
        assert mock_tenacity_sleep.call_count == 0


def test_get_max_retries_override(wrapper: HTTPClientWrapper) -> None:
    """Verify that the max_retries parameter in get() overrides the instance default."""
    request_obj = httpx.Request("GET", "https://api.test.com")

    with (
        patch.object(wrapper.client, "get") as mock_get,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_get.side_effect = httpx.ConnectError("Down", request=request_obj)

        # Override instance default (3) with a single attempt
        with pytest.raises(httpx.ConnectError):
            wrapper.get("https://api.test.com", max_retries=1)

        assert mock_get.call_count == 1


def test_get_with_custom_headers(wrapper: HTTPClientWrapper) -> None:
    """Verify that custom headers are correctly passed to the httpx call."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "get", return_value=mock_response) as mock_get:
        custom_headers = {"Accept": "text/x-bibliography"}
        wrapper.get("https://api.test.com", headers=custom_headers)

        mock_get.assert_called_once_with(
            "https://api.test.com",
            params={"mailto": "test@example.com"},
            headers=custom_headers,
        )


def test_get_follows_redirects(wrapper: HTTPClientWrapper) -> None:
    """Verify that the underlying client correctly follows HTTP redirects (302)."""
    request_initial = httpx.Request("GET", "https://doi.org/10.1038/sample")
    request_redirected = httpx.Request("GET", "https://api.crossref.org/transform")

    response_302 = httpx.Response(
        status_code=302,
        headers={"Location": "https://api.crossref.org/transform"},
        request=request_initial,
    )

    response_200 = httpx.Response(
        status_code=200,
        text="Ceci est la référence finale",
        request=request_redirected,
    )

    response_200.history.append(response_302)

    with patch.object(wrapper.client, "get", return_value=response_200) as mock_get:
        response = wrapper.get("https://doi.org/10.1038/sample")

        assert response.status_code == 200
        assert response.text == "Ceci est la référence finale"
        assert len(response.history) == 1
        assert response.history[0].status_code == 302
        mock_get.assert_called_once()


def test_get_accepts_and_converts_pydantic_http_url(wrapper: HTTPClientWrapper) -> None:
    """Verify that the get method explicitly converts a Pydantic HttpUrl object
    into a primitive string before passing it to the HTTPX client.
    """
    url_raw = "https://api.crossref.org/styles"
    # Creation of a Pydantic HttpUrl (Pydantic v2)
    pydantic_url = TypeAdapter(networks.HttpUrl).validate_python(url_raw)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(
        wrapper.client, "get", return_value=mock_response
    ) as mock_httpx_get:
        response = wrapper.get(url=pydantic_url)

        assert response.status_code == 200

        called_args, _ = mock_httpx_get.call_args
        actual_url_passed = called_args[0]

        assert isinstance(actual_url_passed, str)
        assert actual_url_passed == url_raw
