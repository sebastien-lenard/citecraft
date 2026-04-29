import unittest
from unittest.mock import patch, MagicMock
from journal_fetcher import JournalFetcher

class TestJournalFetcher(unittest.TestCase):

    def setUp(self):
        # Initialize the fetcher; we will mock the methods that use config_loader values
        self.fetcher = JournalFetcher()

    @patch('journal_fetcher.time.sleep', return_value=None)  # Bypass delay
    @patch('journal_fetcher.requests.get')
    def test_get_issns_and_dates_by_name_success(self, mock_get, mock_sleep):
        # 1. Setup mock for the main search call
        mock_response_main = MagicMock()
        mock_response_main.status_code = 200
        mock_response_main.json.return_value = {
            'message': {
                'items': [{
                    'title': 'Geology',
                    'publisher': 'GSB',
                    'ISSN': ['0091-7613']
                }]
            }
        }

        # 2. Setup mock for the ISSN endpoint calls (min and max years)
        mock_response_year = MagicMock()
        mock_response_year.status_code = 200
        mock_response_year.json.return_value = {
            'message': {
                'items': [{
                    'published-print': {'date-parts': [[1973]]},
                    'published-online': {'date-parts': [[1995]]}
                }]
            }
        }

        # Configure mock_get to return these in order
        mock_get.side_effect = [mock_response_main, mock_response_year, mock_response_year]

        results = self.fetcher.get_issns_and_dates_by_name("Geology")

        # Assertions
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['issn'], '0091-7613')
        self.assertEqual(results[0]['start_year'], 1973)
        self.assertEqual(results[0]['end_year'], 1995)
        self.assertEqual(mock_sleep.call_count, 3) # Once for main, twice for years

    @patch('journal_fetcher.requests.get')
    def test_get_issns_and_dates_by_name_no_results(self, mock_get):
        # Simulate empty response from Crossref
        mock_response = MagicMock()
        mock_response.json.return_value = {'message': {'items': []}}
        mock_get.return_value = mock_response

        results = self.fetcher.get_issns_and_dates_by_name("NonExistentJournal")
        self.assertIsNone(results)

    @patch('journal_fetcher.requests.get')
    def test_get_year_endpoint_error_handling(self, mock_get):
        # Simulate an API timeout or error
        mock_get.side_effect = Exception("Connection Error")
        
        year = self.fetcher.get_year_endpoint("0000-0000", "asc")
        self.assertIsNone(year)
    
    @patch('journal_fetcher.time.sleep', return_value=None)
    @patch('journal_fetcher.requests.get')
    def test_get_issns_and_dates_multiple_issns(self, mock_get, mock_sleep):
        """Tests that a journal with 2 ISSNs returns 2 distinct records."""
        
        # 1. Mock the main journal search (returns 2 ISSNs)
        mock_main_resp = MagicMock()
        mock_main_resp.status_code = 200
        mock_main_resp.json.return_value = {
            'message': {
                'items': [{
                    'title': 'Nature',
                    'publisher': 'Springer Nature',
                    'ISSN': ['0028-0836', '1476-4687']
                }]
            }
        }

        # 2. Mock the 4 subsequent calls to get_year_endpoint
        # (2 calls per ISSN: one for 'asc', one for 'desc')
        def year_response(year):
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {
                'message': {
                    'items': [{
                        'published-print': {'date-parts': [[year]]}
                    }]
                }
            }
            return m

        # Side effect sequence: [Main Search, ISSN1-min, ISSN1-max, ISSN2-min, ISSN2-max]
        mock_get.side_effect = [
            mock_main_resp,
            year_response(1869), year_response(2023), # ISSN 0028-0836
            year_response(1997), year_response(2023)  # ISSN 1476-4687
        ]

        results = self.fetcher.get_issns_and_dates_by_name("Nature")

        # ASSERTIONS
        self.assertEqual(len(results), 2, "Should return one record for each ISSN")
        
        # Verify first ISSN record
        self.assertEqual(results[0]['issn'], '0028-0836')
        self.assertEqual(results[0]['start_year'], 1869)
        
        # Verify second ISSN record
        self.assertEqual(results[1]['issn'], '1476-4687')
        self.assertEqual(results[1]['start_year'], 1997)

        # Total API calls should be 5 (1 main + 4 year checks)
        self.assertEqual(mock_get.call_count, 5)

if __name__ == '__main__':
    unittest.main()
