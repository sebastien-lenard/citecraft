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


def test_validate_favored_style_success(mock_styles_response: MagicMock) -> None:
    """Verify favored_style_is_valid is True when the style is supported."""

    repo = StyleRepository("apa")
    with patch.object(
        repo.requests_wrapper, "get", return_value=mock_styles_response
    ) as mock_get:
        repo.validate_favored_style()
        assert repo.favored_style_is_valid is True
        assert mock_get.call_count == 1


def test_validate_favored_style_favored_style_failure(
    mock_styles_response: MagicMock,
) -> None:
    """Verify favored_style_is_valid is False when the style is not supported."""

    repo = StyleRepository("not-a-real-style")
    with patch.object(repo.requests_wrapper, "get", return_value=mock_styles_response):
        repo.validate_favored_style()
        assert repo.favored_style_is_valid is False
