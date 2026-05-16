import logging
import time

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

# Define a logger for this module
logger = logging.getLogger(__name__)


class HTTPClientWrapper:
    def __init__(
        self,
        email: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: int = 2,
        delay: float = 1.0,
    ):
        """Initialize the wrapper with API politeness and retry logic parameters."""
        self.email = email
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.delay = delay
        self.client = httpx.Client(
            timeout=httpx.Timeout(self.timeout), follow_redirects=True
        )

    def _is_transient_error(self, exception: Exception) -> bool:
        """Check if error is temporary and should be followed by retry.
        Examples:
        - Transport errors: Timeout, deconnection
        - Status errors: HTTP 429 response (Rate Limited) or server error (5xx).
        """
        if isinstance(exception, httpx.TransportError):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            return status == 429 or status >= 500
        return False

    def _log_retry(self, retry_state):
        """Native Tenacity callback called before waiting new attempt."""
        url = retry_state.args[0] if retry_state.args else "unknown"
        error = (
            retry_state.outcome.exception()
            if retry_state.outcome
            else "Transient failure"
        )
        logger.warning(
            "Transient error encountered. Retrying request to %s (Attempt %d). "
            "Error: %s",
            url,
            retry_state.attempt_number,
            error,
        )

    def get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        max_retries: int | None = None,
    ) -> httpx.Response:
        """Performs a GET request with retry logic with Tenacity strategy.
        Fatal errors (like 401, 403, 404) raise immediately.
        """
        url = str(url)
        params = params or {}
        headers = headers or {}

        limit_attempts = max_retries if max_retries is not None else self.max_retries

        # Add politeness mailto if not already present
        if self.email and "mailto" not in params:
            params["mailto"] = self.email

        # Respect initial courtesy delay for the very first call
        if self.delay > 0:
            time.sleep(self.delay)

        # Tenacity strategy configuration
        retrier = Retrying(
            stop=stop_after_attempt(limit_attempts),
            wait=wait_exponential(multiplier=self.backoff_factor, min=1, max=10),
            retry=retry_if_exception(self._is_transient_error),
            before_sleep=self._log_retry,
            reraise=True,
        )

        try:
            return retrier(self.client.get, url, params=params, headers=headers)

        except httpx.HTTPStatusError as e:
            logger.error("Fatal or unresolved HTTP Error for URL %s: %s", url, e)
            raise e
        except Exception as e:
            logger.error(
                "Unexpected or unrecoverable error during request to %s: %s", url, e
            )
            raise e

    def close(self) -> None:
        """Close the underlying HTTPX client."""
        self.client.close()
