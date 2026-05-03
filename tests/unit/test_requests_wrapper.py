from unittest.mock import MagicMock, patch

import pytest
import requests

from manuscript_reference_lister import RequestsWrapper


@pytest.fixture
def wrapper() -> RequestsWrapper:
    """Provides a RequestsWrapper instance with low backoff for fast testing."""
    return RequestsWrapper(email="test@example.com", max_retries=3, backoff_factor=0.1)


def test_get_success(wrapper: RequestsWrapper) -> None:
    """Verify that a successful request returns the response immediately."""
    with patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get:
        mock_response = MagicMock(status_code=200)
        mock_get.return_value = mock_response

        response = wrapper.get("https://api.test.com")

        assert response == mock_response
        assert mock_get.call_count == 1


def test_get_retry_on_timeout(wrapper: RequestsWrapper) -> None:
    """Verify that the wrapper retries upon receiving a Timeout exception."""
    # Simulate two failures followed by one success
    with (
        patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get,
        patch("manuscript_reference_lister.requests_wrapper.time.sleep") as mock_sleep,
    ):
        mock_get.side_effect = [
            requests.exceptions.Timeout("Slow connection"),
            requests.exceptions.Timeout("Still slow"),
            MagicMock(status_code=200),
        ]

        wrapper.get("https://api.test.com")

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 3  # Initial delay + 2 retries


def test_get_max_retries_reached(wrapper: RequestsWrapper) -> None:
    """Verify the wrapper raises the last exception after max retries are exhausted."""
    with (
        patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get,
        patch("manuscript_reference_lister.requests_wrapper.time.sleep"),
    ):
        mock_get.side_effect = requests.exceptions.ConnectionError("Down")

        with pytest.raises(requests.exceptions.ConnectionError):
            wrapper.get("https://api.test.com")

        assert mock_get.call_count == 3


def test_get_fatal_http_error(wrapper: RequestsWrapper) -> None:
    """Verify that fatal HTTP errors (like 404) raise immediately without retry."""
    with patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            wrapper.get("https://api.test.com")

        # Fatal errors should stop at the first attempt
        assert mock_get.call_count == 1


def test_get_max_retries_override(wrapper: RequestsWrapper) -> None:
    """Verify that the max_retries parameter in get() overrides the instance default."""
    with (
        patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get,
        patch("manuscript_reference_lister.requests_wrapper.time.sleep") as mock_sleep,
    ):
        mock_get.side_effect = requests.exceptions.ConnectionError("Down")

        # Override instance default (3) with a single attempt
        with pytest.raises(requests.exceptions.ConnectionError):
            wrapper.get("https://api.test.com", max_retries=1)

        assert mock_get.call_count == 1
        assert mock_sleep.call_count == 1


def test_get_with_custom_headers(wrapper: RequestsWrapper) -> None:
    """Verify that custom headers are correctly passed to the requests call."""
    with patch("manuscript_reference_lister.requests_wrapper.requests.get") as mock_get:
        mock_response = MagicMock(status_code=200)
        mock_get.return_value = mock_response

        custom_headers = {"Accept": "text/x-bibliography"}
        wrapper.get("https://api.test.com", headers=custom_headers)

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == custom_headers
