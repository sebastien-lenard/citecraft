import unittest
from unittest.mock import patch, MagicMock
import requests
from requests_wrapper import RequestsWrapper

class TestRequestsWrapper(unittest.TestCase):
    def setUp(self):
        self.wrapper = RequestsWrapper(email="test@example.com", max_retries=3, backoff_factor=1)

    @patch('requests_wrapper.requests.get')
    def test_get_success(self, mock_get):
        """
        Test that a successful request returns the response immediately.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        response = self.wrapper.get("https://api.test.com")
        
        self.assertEqual(response, mock_response)
        self.assertEqual(mock_get.call_count, 1)

    @patch('requests_wrapper.time.sleep', return_value=None) # Skip actual waiting
    @patch('requests_wrapper.requests.get')
    def test_get_retry_on_timeout(self, mock_get, mock_sleep):
        """
        Test that the wrapper retries upon receiving a Timeout exception.
        Note: Total sleeps = 1 (initial delay) + 2 (retries).
        """
        # Simulate two failures then one success
        mock_get.side_effect = [
            requests.exceptions.Timeout("Slow connection"),
            requests.exceptions.Timeout("Still slow"),
            MagicMock(status_code=200)
        ]

        response = self.wrapper.get("https://api.test.com")
        
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 3)

    @patch('requests_wrapper.time.sleep', return_value=None)
    @patch('requests_wrapper.requests.get')
    def test_get_max_retries_reached(self, mock_get, mock_sleep):
        """
        Test that the wrapper eventually raises the last exception after max retries.
        """
        mock_get.side_effect = requests.exceptions.ConnectionError("Down")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.wrapper.get("https://api.test.com")
        
        self.assertEqual(mock_get.call_count, 3)

    @patch('requests_wrapper.requests.get')
    def test_get_fatal_http_error(self, mock_get):
        """
        Test that HTTP errors like 404 (Not Found) raise immediately without retry.
        """
        mock_response = MagicMock()
        # Mocking raise_for_status to raise an HTTPError
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.wrapper.get("https://api.test.com")
        
        # Should not retry for a 404
        self.assertEqual(mock_get.call_count, 1)

    @patch('requests_wrapper.time.sleep', return_value=None)
    @patch('requests_wrapper.requests.get')
    def test_get_max_retries_override(self, mock_get, mock_sleep):
        """
        Test that the max_retries parameter in get() overrides the instance default.
        """
        # On simule une erreur de connexion persistante
        mock_get.side_effect = requests.exceptions.ConnectionError("Down")

        # On appelle get avec une surcharge à 1 seule tentative
        # (alors que self.wrapper.max_retries est à 3 dans le setUp)
        with self.assertRaises(requests.exceptions.ConnectionError):
            self.wrapper.get("https://api.test.com", max_retries=1)
        
        # On vérifie que le wrapper n'a essayé qu'une seule fois
        self.assertEqual(mock_get.call_count, 1)
        # 1 seul sleep (celui de la politesse initiale)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('requests_wrapper.requests.get')
    def test_get_with_custom_headers(self, mock_get):
        """
        Test that custom headers are correctly passed to the requests call.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        custom_headers = {'Accept': 'text/x-bibliography'}
        self.wrapper.get("https://api.test.com", headers=custom_headers)

        # Vérifie que requests.get a été appelé avec les headers fournis
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs['headers'], custom_headers)
