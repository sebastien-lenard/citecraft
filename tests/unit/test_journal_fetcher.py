import logging
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from manuscript_reference_lister import JournalFetcher, config_loader

logging.basicConfig(level=logging.WARNING)


class TestJournalFetcher(unittest.TestCase):
    def setUp(self):
        # Initialize the fetcher; we will mock the methods that use config_loader values
        self.fetcher = JournalFetcher()
        self.work_dir_path = config_loader.TEST_WORK_DIR_PATH

    @patch("manuscript_reference_lister.journal_fetcher.RequestsWrapper.get")
    def test_get_issns_and_dates_by_name_success(self, mock_wrapper_get):
        # 1. Setup mock for the main search call
        mock_response_main = MagicMock()
        mock_response_main.status_code = 200
        mock_response_main.json.return_value = {
            "message": {
                "items": [
                    {"title": "Geology", "publisher": "GSB", "ISSN": ["0091-7613"]}
                ]
            }
        }

        # 2. Setup mock for the ISSN endpoint calls (min and max years)
        mock_response_year = MagicMock()
        mock_response_year.status_code = 200
        mock_response_year.json.return_value = {
            "message": {
                "items": [
                    {
                        "published-print": {"date-parts": [[1973]]},
                        "published-online": {"date-parts": [[1995]]},
                    }
                ]
            }
        }

        # Configure mock_get to return these in order
        mock_wrapper_get.side_effect = [
            mock_response_main,
            mock_response_year,
            mock_response_year,
        ]

        results = self.fetcher.get_issns_and_dates_by_name("Geology")

        # Assertions
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["issn"], "0091-7613")
        self.assertEqual(results[0]["start_year"], 1973)
        self.assertEqual(results[0]["end_year"], 1995)

    @patch("manuscript_reference_lister.journal_fetcher.RequestsWrapper.get")
    def test_get_issns_and_dates_by_name_not_found_behavior(self, mock_wrapper_get):
        """
        Test the behavior when Crossref returns no items or no exact matches.
        Verifies that the logic correctly falls back to a template and logs a warning.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"items": []}}
        mock_wrapper_get.return_value = mock_response

        # Using assertLogs(level='WARNING') as established during debug
        with self.assertLogs(level="WARNING") as cm:
            results = self.fetcher.get_issns_and_dates_by_name("Unknown Journal")
            # Verify the log was captured
            self.assertTrue(
                any("Unknown Journal not found" in output for output in cm.output)
            )

        # Verify data integrity
        self.assertEqual(
            len(results), 1, "Should return a list with one template dictionary"
        )
        self.assertIsNone(results[0]["issn"])
        self.assertEqual(results[0]["requested_title"], "Unknown Journal")
        # On vérifie que c'est bien notre wrapper qui a été appelé
        mock_wrapper_get.assert_called_once()

    @patch("manuscript_reference_lister.journal_fetcher.RequestsWrapper.get")
    def test_get_year_endpoint_error_handling(self, mock_wrapper_get):
        # Simulate an API timeout or error
        mock_wrapper_get.side_effect = Exception("Connection Error")

        year = self.fetcher.get_year_endpoint("0000-0000", "asc")
        self.assertIsNone(year)

    @patch("manuscript_reference_lister.journal_fetcher.RequestsWrapper.get")
    def test_get_issns_and_dates_multiple_issns(self, mock_wrapper_get):
        """Tests that a journal with 2 ISSNs returns 2 distinct records."""

        # 1. Mock the main journal search (returns 2 ISSNs)
        mock_main_resp = MagicMock()
        mock_main_resp.status_code = 200
        mock_main_resp.json.return_value = {
            "message": {
                "items": [
                    {
                        "title": "Nature",
                        "publisher": "Springer Nature",
                        "ISSN": ["0028-0836", "1476-4687"],
                    }
                ]
            }
        }

        # 2. Mock the 4 subsequent calls to get_year_endpoint
        # (2 calls per ISSN: one for 'asc', one for 'desc')
        def year_response(year):
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {
                "message": {"items": [{"published-print": {"date-parts": [[year]]}}]}
            }
            return m

        # Side effect sequence: [Main Search, ISSN1-min, ISSN1-max, ISSN2-min, ISSN2-max]
        mock_wrapper_get.side_effect = [
            mock_main_resp,
            year_response(1869),
            year_response(2023),  # ISSN 0028-0836
            year_response(1997),
            year_response(2023),  # ISSN 1476-4687
        ]

        results = self.fetcher.get_issns_and_dates_by_name("Nature")

        # ASSERTIONS
        self.assertEqual(len(results), 2, "Should return one record for each ISSN")

        # Verify first ISSN record
        self.assertEqual(results[0]["issn"], "0028-0836")
        self.assertEqual(results[0]["start_year"], 1869)

        # Verify second ISSN record
        self.assertEqual(results[1]["issn"], "1476-4687")
        self.assertEqual(results[1]["start_year"], 1997)

        # Total API calls should be 5 (1 main + 4 year checks)
        self.assertEqual(mock_wrapper_get.call_count, 5)

    @patch(
        "manuscript_reference_lister.journal_fetcher.open",
        new_callable=unittest.mock.mock_open,
        read_data="[]",
    )
    def test_load_and_merge_journal_info_list_with_test_path(self, mock_file):
        """
        Test loading and merging functionality using the TEST_WORK_DIR_PATH.
        Verifies that new titles are added as empty templates and existing ones are preserved.
        """
        self.fetcher.work_dir_path = self.work_dir_path

        # Simulate existing local data
        self.fetcher.journal_info_list = [
            {"requested_title": "Existing Journal", "issn": "0000-0000"}
        ]

        input_list = ["Existing Journal", "New Journal"]

        # Execute merge
        self.fetcher.load_and_merge_journal_info_list(journal_title_list=input_list)

        # Assertions
        self.assertEqual(len(self.fetcher.journal_info_list), 2)

        # Check if the new entry is correctly initialized with None values
        new_entry = next(
            item
            for item in self.fetcher.journal_info_list
            if item["requested_title"] == "New Journal"
        )
        self.assertIsNone(new_entry["issn"])
        self.assertEqual(new_entry["update"], str(date.today()))

    @patch("manuscript_reference_lister.journal_fetcher.json.dump")
    @patch(
        "manuscript_reference_lister.journal_fetcher.open",
        new_callable=unittest.mock.mock_open,
    )
    def test_save_journal_info_list_to_test_dir(self, mock_file, mock_json_dump):
        """
        Verify that saving the journal list targets the correct test directory
        and uses the expected JSON format.
        """
        self.fetcher.work_dir_path = self.work_dir_path
        self.fetcher.journal_info_list = [{"requested_title": "Test", "issn": "1234"}]

        expected_path = Path(self.fetcher.work_dir_path) / "journal_info_list.json"

        self.fetcher.save_journal_info_list()

        # Verify the file was opened with the correct path
        mock_file.assert_called_once_with(expected_path, "w")
        mock_json_dump.assert_called_once()

    @patch(
        "manuscript_reference_lister.journal_fetcher.JournalFetcher."
        "get_issns_and_dates_by_name"
    )
    def test_update_journal_info_priority_and_limit(self, mock_get_info):
        """
        Test that update_journal_info respects the maximum number of API calls
        and prioritizes records with missing (None) information.
        """
        # Setup: 1 missing, 1 old, 1 recent. Set limit to 1 call.
        self.fetcher.update_max = 1
        self.fetcher.update_days = 30

        today = date.today()
        old_date_str = str(today - timedelta(days=45))
        recent_date_str = str(today - timedelta(days=5))

        self.fetcher.journal_info_list = [
            {
                "requested_title": "Old Journal",
                "update": old_date_str,
                "issn": "1234-5678",
            },
            {
                "requested_title": "Missing Journal",
                "update": recent_date_str,
                "issn": None,
            },  # Priority 1
            {
                "requested_title": "Recent Journal",
                "update": recent_date_str,
                "issn": "9012-3456",
            },
        ]

        # Mock returns updated data for the priority target
        mock_get_info.return_value = [
            {
                "requested_title": "Missing Journal",
                "issn": "1111-2222",
                "update": str(today),
                "title": "Missing Journal",
                "publisher": "Pub",
                "start_year": 2000,
                "end_year": 2024,
            }
        ]

        self.fetcher.update_journal_info()

        # Assertions: Only one call should have been made to the API method
        self.assertEqual(mock_get_info.call_count, 1)
        self.assertTrue(self.fetcher.has_pending_updates)

        # Verify that the 'Missing' journal was the one processed
        processed_titles = [
            r["requested_title"]
            for r in self.fetcher.journal_info_list
            if r.get("issn") == "1111-2222"
        ]
        self.assertIn("Missing Journal", processed_titles)


if __name__ == "__main__":
    unittest.main()
