# tests/unit/network/test_http_client_wrapper.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests verifying request routing and error boundaries for the network client."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import httpx
import pytest
from pydantic import TypeAdapter, networks

from citecraft.network.http_client_wrapper import HTTPClientConfig, HTTPClientWrapper


@pytest.fixture
def wrapper() -> Generator[HTTPClientWrapper, None, None]:
    """Provide HTTPClientWrapper with low backoffs for deterministic tests."""
    client_options = HTTPClientConfig(max_retries=3, backoff_factor=0.01, delay=0.0)
    client_wrapper = HTTPClientWrapper(
        email="test@example.com",
        client_config=client_options,
    )
    yield client_wrapper
    client_wrapper.close()


def test_get_success(wrapper: HTTPClientWrapper) -> None:
    """Verify that a successful request returns the response immediately."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "send", return_value=mock_response) as mock_send:
        response, predicted_url = wrapper.get("https://api.test.com")

        assert response == mock_response
        assert mock_send.call_count == 1
        host = urlparse(predicted_url).hostname
        assert host == "api.test.com"


@pytest.mark.parametrize(
    "errors_to_simulate",
    [
        # Scenario A: Network timeout retry sequences
        [
            httpx.ReadTimeout(
                "Timeout",
                request=httpx.Request("GET", "https://api.test.com"),
            ),
            httpx.ReadTimeout(
                "Timeout 2",
                request=httpx.Request("GET", "https://api.test.com"),
            ),
        ],
        # Scenario B: Transient HTTP status errors (429, 503)
        [
            httpx.HTTPStatusError(
                "Too Many Requests",
                request=httpx.Request("GET", "https://api.test.com"),
                response=httpx.Response(429),
            ),
            httpx.HTTPStatusError(
                "Service Unavailable",
                request=httpx.Request("GET", "https://api.test.com"),
                response=httpx.Response(503),
            ),
        ],
    ],
)
def test_get_retry_on_transient_failures(
    wrapper: HTTPClientWrapper,
    errors_to_simulate: list[Exception],
) -> None:
    """Verify wrapper retries transient failures before returning success."""
    mock_response_ok = MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200

    with (
        patch.object(wrapper.client, "send") as mock_send,
        patch("tenacity.nap.time.sleep") as mock_tenacity_sleep,
    ):
        mock_send.side_effect = [*errors_to_simulate, mock_response_ok]

        response, _ = wrapper.get("https://api.test.com")

        assert response == mock_response_ok
        assert mock_send.call_count == len(errors_to_simulate) + 1
        assert mock_tenacity_sleep.call_count == len(errors_to_simulate)


def test_get_max_retries_reached(wrapper: HTTPClientWrapper) -> None:
    """Verify the wrapper raises the last exception after max retries are exhausted."""
    request_obj = httpx.Request("GET", "https://api.test.com")

    with (
        patch.object(wrapper.client, "send") as mock_send,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_send.side_effect = httpx.ConnectError("Down", request=request_obj)

        with pytest.raises(httpx.ConnectError):
            wrapper.get("https://api.test.com")

        assert mock_send.call_count == 3


@pytest.mark.parametrize("fatal_status_code", [400, 401, 403, 404])
def test_get_fatal_http_errors_raise_immediately(
    wrapper: HTTPClientWrapper,
    fatal_status_code: int,
) -> None:
    """Verify that fatal HTTP errors do not trigger retry attempts and fail loudly."""
    mock_response = httpx.Response(fatal_status_code)
    request_obj = httpx.Request("GET", "https://api.test.com")
    error_fatal = httpx.HTTPStatusError(
        f"Error {fatal_status_code}",
        request=request_obj,
        response=mock_response,
    )

    with (
        patch.object(wrapper.client, "send", side_effect=error_fatal) as mock_send,
        patch("tenacity.nap.time.sleep") as mock_tenacity_sleep,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            wrapper.get("https://api.test.com")

        assert mock_send.call_count == 1
        assert mock_tenacity_sleep.call_count == 0


def test_get_max_retries_override(wrapper: HTTPClientWrapper) -> None:
    """Verify that the max_retries parameter in get() overrides the default limit."""
    request_obj = httpx.Request("GET", "https://api.test.com")

    with (
        patch.object(wrapper.client, "send") as mock_send,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_send.side_effect = httpx.ConnectError("Down", request=request_obj)

        with pytest.raises(httpx.ConnectError):
            wrapper.get("https://api.test.com", max_retries=1)

        assert mock_send.call_count == 1


def test_get_with_custom_headers(wrapper: HTTPClientWrapper) -> None:
    """Verify custom headers are forwarded intact to client requests."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "send", return_value=mock_response) as mock_send:
        custom_headers = {"Accept": "text/x-bibliography"}
        wrapper.get("https://api.test.com", headers=custom_headers)

        mock_send.assert_called_once()
        called_request = mock_send.call_args[0][0]
        assert called_request.headers["Accept"] == "text/x-bibliography"
        assert "mailto=test%40example.com" in str(called_request.url)


def test_get_follows_redirects(wrapper: HTTPClientWrapper) -> None:
    """Verify the client traces redirect hops to final destination responses."""
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

    with patch.object(wrapper.client, "send", return_value=response_200) as mock_send:
        response, _ = wrapper.get("https://doi.org/10.1038/sample")

        assert response is not None
        assert response.status_code == 200
        assert response.text == "Ceci est la référence finale"
        assert len(response.history) == 1
        assert response.history[0].status_code == 302
        mock_send.assert_called_once()


def test_get_accepts_and_converts_pydantic_http_url(
    wrapper: HTTPClientWrapper,
) -> None:
    """Verify get handler converts Pydantic HttpUrl to standard representations."""
    url_raw = "https://api.crossref.org/styles"
    pydantic_url = TypeAdapter(networks.HttpUrl).validate_python(url_raw)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "send", return_value=mock_response) as mock_send:
        url_arg: Any = pydantic_url
        response, _ = wrapper.get(url=url_arg)

        assert response is not None
        assert response.status_code == 200

        mock_send.assert_called_once()
        called_request = mock_send.call_args[0][0]
        assert str(called_request.url).startswith(url_raw)


def test_get_max_url_length_exceeded(
    wrapper: HTTPClientWrapper,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that exceeding the URL limit prevents the request and logs a warning."""
    wrapper.url_max_character_length = 10

    response, predicted_url = wrapper.get("https://api.test.com/some/very/long/path")

    assert response is None
    assert len(predicted_url) > 10
    assert any("Request not sent" in record.message for record in caplog.records)


def test_get_retry_on_transient_failures_logging(
    wrapper: HTTPClientWrapper,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that retries on transient errors log warning messages."""
    mock_response_ok = MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200

    error = httpx.ReadTimeout(
        "Timeout",
        request=httpx.Request("GET", "https://api.test.com"),
    )

    with (
        patch.object(wrapper.client, "send") as mock_send,
        patch("tenacity.nap.time.sleep"),
    ):
        mock_send.side_effect = [error, mock_response_ok]

        wrapper.get("https://api.test.com")

        assert any("Transient error encountered" in r.message for r in caplog.records)


def test_get_fatal_http_errors_logging(
    wrapper: HTTPClientWrapper,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that fatal HTTP status errors log error messages."""
    mock_response = httpx.Response(404)
    request_obj = httpx.Request("GET", "https://api.test.com")
    error_fatal = httpx.HTTPStatusError(
        "Not Found",
        request=request_obj,
        response=mock_response,
    )

    with patch.object(wrapper.client, "send", side_effect=error_fatal):
        with pytest.raises(httpx.HTTPStatusError):
            wrapper.get("https://api.test.com")

        assert any(
            "Fatal or unresolved HTTP Error" in r.message for r in caplog.records
        )


def test_get_unexpected_errors_logging(
    wrapper: HTTPClientWrapper,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify that unexpected exceptions log errors with traceback info."""
    with patch.object(wrapper.client, "send", side_effect=RuntimeError("Crash")):
        with pytest.raises(RuntimeError):
            wrapper.get("https://api.test.com")

        assert any(
            "Unexpected or unrecoverable error" in r.message for r in caplog.records
        )


def test_get_respects_initial_delay() -> None:
    """Verify that the initial delay triggers a sleep wait sequence."""
    client_options = HTTPClientConfig(delay=0.05, max_retries=1)
    delay_wrapper = HTTPClientWrapper(
        email="test@example.com",
        client_config=client_options,
    )
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with (
        patch.object(delay_wrapper.client, "send", return_value=mock_response),
        patch("time.sleep") as mock_sleep,
    ):
        delay_wrapper.get("https://api.test.com")
        mock_sleep.assert_called_once_with(0.05)

    delay_wrapper.close()


def test_get_custom_mailto_not_overwritten(wrapper: HTTPClientWrapper) -> None:
    """Verify that any pre-existing mailto parameter is preserved intact."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(wrapper.client, "send", return_value=mock_response) as mock_send:
        params = {"mailto": "custom_override@example.com"}
        wrapper.get("https://api.test.com", params=params)

        mock_send.assert_called_once()
        called_request = mock_send.call_args[0][0]
        # Custom mailto should not be replaced with the default wrapper.email
        assert "mailto=custom_override%40example.com" in str(called_request.url)
        assert "test%40example.com" not in str(called_request.url)
