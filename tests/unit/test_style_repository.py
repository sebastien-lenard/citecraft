from unittest.mock import MagicMock, patch

import pytest

from manuscript_reference_lister import StyleRepository


@pytest.fixture
def mock_styles_response():
    """Provides a standard successful API response mock."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "message": {"items": ["apa", "harvard3", "ieee", "nature"]}
    }
    return mock


@patch("manuscript_reference_lister.style_repository.RequestsWrapper.get")
def test_check_style_is_valid_success(
    mock_wrapper_get: MagicMock, mock_styles_response: MagicMock
) -> None:
    """Verify style_is_valid is True when the style exists in the API response."""
    mock_wrapper_get.return_value = mock_styles_response

    repo = StyleRepository("apa")
    repo.check_style_is_valid()

    assert repo.style_is_valid is True
    assert mock_wrapper_get.call_count == 1


@patch("manuscript_reference_lister.style_repository.RequestsWrapper.get")
def test_check_style_is_valid_failure(
    mock_wrapper_get: MagicMock, mock_styles_response: MagicMock
) -> None:
    """Verify style_is_valid is False when the style is missing from API response."""
    mock_wrapper_get.return_value = mock_styles_response

    repo = StyleRepository("not-a-real-style")
    repo.check_style_is_valid()

    assert repo.style_is_valid is False
