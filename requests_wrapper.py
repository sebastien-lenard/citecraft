import time
import requests
import logging

# Define a logger for this module
logger = logging.getLogger(__name__)

class RequestsWrapper:
    def __init__(self, email, timeout=30, max_retries=3, backoff_factor=2, delay=1.0):
        """
        Initialize the wrapper with API politeness and retry logic parameters.
        delay: Time to wait (in seconds) before each initial request to respect API limits.
        """
        self.email = email
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.delay = delay

    def get(self, url, params=None, headers=None, max_retries=None):
        """
        Performs a GET request with retry logic for network-related errors.
        Fatal errors (like 404 or malformed responses) raise immediately.
        """
        if params is None:
            params = {}
        if headers is None:
            headers = {}
        
        retries = max_retries if max_retries is not None else self.max_retries
            
        # Add politeness mailto if not already present
        if self.email and "mailto" not in params:
            params["mailto"] = self.email

        last_exception = None
        
        for attempt in range(self.max_retries):
            # 1. We apply the safety delay before the actual request
            if attempt == 0 and self.delay > 0:
                time.sleep(self.delay)
            try:
                response = requests.get(url, params=params, headers=headers,
                                        timeout=self.timeout)
                
                # If we get a 4xx or 5xx, this raises an HTTPError
                response.raise_for_status()
                
                # Success: return the response object
                return response

            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError) as e:
                last_exception = e
                wait_time = self.backoff_factor ** attempt
                
                logger.warning(
                    "Network error on attempt %d/%d for URL %s. Retrying in %ds. Error: %s",
                    attempt + 1, self.max_retries, url, wait_time, e
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
            
            except requests.exceptions.HTTPError as e:
                # Fatal HTTP errors (like 401, 404, 403) are usually not solved by retrying
                logger.error("Fatal HTTP Error for URL %s: %s", url, e)
                raise e
                
            except Exception as e:
                # Any other unexpected error is fatal
                logger.error("Unexpected error during request to %s: %s", url, e)
                raise e

        # If we reach here, it means all retries failed
        logger.error("All %d retries failed for URL %s", self.max_retries, url)
        raise last_exception
