import unittest
from unittest.mock import patch, MagicMock
from doi_fetcher import DoiFetcher

class TestDoiFetcher(unittest.TestCase):

    def setUp(self):
        self.fetcher = DoiFetcher()

    @patch('doi_fetcher.time.sleep', return_value=None)
    @patch('doi_fetcher.requests.get')
    def test_get_formatted_reference_success(self, mock_get, mock_sleep):
        # Mocking a successful plain text response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Doe, J. (2023). Title of the Paper. Journal of Science."
        mock_get.return_value = mock_response

        doi = "10.1000/182"
        style = "apa"
        result = self.fetcher.get_formatted_reference(doi, style)

        self.assertEqual(result, "Doe, J. (2023). Title of the Paper. Journal of Science.")
        # Ensure the headers were set correctly for content negotiation
        args, kwargs = mock_get.call_args
        self.assertIn('headers', kwargs)
        self.assertEqual(kwargs['headers']['Accept'], f"text/x-bibliography; style={style}")

    @patch('doi_fetcher.time.sleep', return_value=None)
    @patch('doi_fetcher.requests.get')
    def test_get_formatted_reference_not_found(self, mock_get, mock_sleep):
        # Mocking a 404 error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.fetcher.get_formatted_reference("invalid/doi", "apa")
        self.assertEqual(result, "Reference unavailable in doi.org.")

if __name__ == '__main__':
    unittest.main()
