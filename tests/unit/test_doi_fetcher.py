import unittest
from unittest.mock import MagicMock, patch

import requests

from manuscript_reference_lister import DoiFetcher


class TestDoiFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = DoiFetcher()

    @patch("manuscript_reference_lister.doi_fetcher.RequestsWrapper.get")
    def test_get_formatted_reference_success(self, mock_wrapper_get):
        # Mocking a successful plain text response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Doe, J. (2023). Title of the Paper. Journal of Science."
        mock_wrapper_get.return_value = mock_response

        doi = "10.1000/182"
        style = "apa"
        result = self.fetcher.get_formatted_reference(doi, style)

        self.assertEqual(
            result, "Doe, J. (2023). Title of the Paper. Journal of Science."
        )
        # Ensure the headers were set correctly for content negotiation
        args, kwargs = mock_wrapper_get.call_args
        self.assertIn("headers", kwargs)
        self.assertEqual(
            kwargs["headers"]["Accept"], f"text/x-bibliography; style={style}"
        )

    @patch("manuscript_reference_lister.doi_fetcher.RequestsWrapper.get")
    def test_get_formatted_reference_not_found(self, mock_wrapper_get):
        # Mocking a 404 error
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = requests.exceptions.HTTPError(
            "404 Client Error", response=mock_response
        )
        mock_wrapper_get.side_effect = error

        result = self.fetcher.get_formatted_reference("invalid/doi", "apa")
        self.assertEqual(result, "Reference unavailable in doi.org.")


if __name__ == "__main__":
    unittest.main()
