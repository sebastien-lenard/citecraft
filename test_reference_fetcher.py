import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import unittest
from unittest.mock import patch, MagicMock
from reference_fetcher import ReferenceFetcher
from config_loader import API_DELAY

class TestReferenceFetcher(unittest.TestCase):
    def setUp(self):
        """Initialize the fetcher for each test."""
        self.fetcher = ReferenceFetcher()

    @patch('reference_fetcher.requests.get')
    @patch('reference_fetcher.time.sleep')
    def test_respect_api_delay(self, mock_sleep, mock_get):
        """Verifies that the program waits for API_DELAY BEFORE making the API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': {'items': []}}
        mock_get.return_value = mock_response

        # Call the new method
        self.fetcher.fetch_apa_candidates("Hovius", "1997")

        mock_sleep.assert_called_once_with(API_DELAY)
        self.assertTrue(mock_get.called)

    @patch('reference_fetcher.requests.get')
    def test_fetch_not_found(self, mock_get):
        """Checks behavior when no results are found (should return empty list)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': {'items': []}}
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_apa_candidates("UnknownAuthor", "2025")
        self.assertEqual(result, [])

    @patch('reference_fetcher.requests.get')
    def test_returns_multiple_candidates_with_scores(self, mock_get):
        """Verifies that the fetcher returns multiple candidates with their Crossref scores."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'items': [
                    {'DOI': '10.1/ref1', 'score': 100.5, 'type': 'journal-article'},
                    {'DOI': '10.1/ref2', 'score': 85.2, 'type': 'proceedings-article'}
                ]
            }
        }
        mock_get.return_value = mock_response
        self.fetcher._get_formatted_apa = MagicMock(return_value="APA String")

        results = self.fetcher.fetch_apa_candidates("Hovius", "1997")
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['score'], 100.5)
        self.assertEqual(results[0]['doi'], "https://doi.org/10.1/ref1")
        self.assertEqual(results[1]['score'], 85.2)

    @patch('reference_fetcher.requests.get')
    def test_parameterized_keywords(self, mock_get):
        """Verifies that custom keywords passed to the method are used in the query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': {'items': []}}
        mock_get.return_value = mock_response

        custom_kws = "landslides mountains"
        self.fetcher.fetch_apa_candidates("Hovius", "1997", keywords=custom_kws)
        
        # Check that the request URL contains our custom keywords
        args, kwargs = mock_get.call_args
        params = kwargs.get('params', {})
        self.assertIn(custom_kws, params.get('query', ''))

if __name__ == '__main__':
    unittest.main()