# src/citecraft/network/http_client_wrapper.py
import logging
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from citecraft.utils import AppConfig, get_config

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HTTPClientConfig:
    """Configuration options parameter packet for HTTPClientWrapper initialization."""

    api_key: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    backoff_factor: float = 2.0
    delay: float | None = None
    url_max_character_length: int | None = None


class HTTPClientWrapper:
    """Synchronous HTTPX client wrapper with Tenacity retry protocols."""

    def __init__(
        self,
        email: str,
        *,
        client_config: HTTPClientConfig | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()
        self.email: str = email

        cfg = client_config or HTTPClientConfig()
        self.api_key: str | None = cfg.api_key if cfg.api_key else None
        self.timeout: float = (
            cfg.timeout if cfg.timeout is not None else self.config.default_api_timeout
        )
        self.max_retries: int = (
            cfg.max_retries
            if cfg.max_retries is not None
            else self.config.default_api_max_retry
        )
        self.backoff_factor: float = cfg.backoff_factor
        self.delay: float = (
            cfg.delay if cfg.delay is not None else self.config.default_api_delay
        )
        self.url_max_character_length: int = (
            cfg.url_max_character_length
            if cfg.url_max_character_length is not None
            else self.config.default_api_url_max_character_length
        )
        self.client: httpx.Client = httpx.Client(
            timeout=httpx.Timeout(self.timeout), follow_redirects=True
        )

    def _is_transient_error(self, exception: BaseException) -> bool:
        """Determine if the exception warrants an automatic retry attempt.
        Examples:
        - Transport errors: Timeout, deconnection
        - Status errors: HTTP 429 response (Rate Limited) or server error (5xx).
        """
        if isinstance(exception, httpx.TransportError):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            return (
                status == HTTPStatus.TOO_MANY_REQUESTS
                or status >= HTTPStatus.INTERNAL_SERVER_ERROR
            )
        return False

    def _log_retry(self, retry_state: RetryCallState) -> None:
        """Log retry attempts triggered by Tenacity state transitions."""
        url = retry_state.args[0] if retry_state.args else "unknown"
        exception = retry_state.outcome.exception() if retry_state.outcome else None

        error_type = type(exception).__name__ if exception else "Transient failure"
        status_code = (
            exception.response.status_code
            if isinstance(exception, httpx.HTTPStatusError)
            else None
        )

        logger.warning(
            "Transient error encountered. Retrying request to %s (Attempt %d). "
            "Error: %s",
            str(url),
            retry_state.attempt_number,
            error_type,
            extra={
                "status": "KO",
                "event": "http_request_retry",
                "url": str(url),
                "attempt": retry_state.attempt_number,
                "error_type": error_type,
                "status_code": status_code,
            },
        )

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int | None = None,
    ) -> tuple[httpx.Response | None, str]:
        """Perform a retried GET request with status verification. Returns response
        and predicted url.
        Fatal errors (like 401, 403, 404) raise immediately.
        """
        target_url = str(url)
        query_params = dict(params) if params is not None else {}
        request_headers = dict(headers) if headers is not None else {}

        limit_attempts = max_retries if max_retries is not None else self.max_retries

        # Add politeness mailto if not already present
        if self.email and "mailto" not in query_params:
            query_params["mailto"] = self.email

        # Respect initial courtesy delay for the very first call
        if self.delay > 0:
            time.sleep(self.delay)

        # Tenacity strategy configuration
        retrier = Retrying(
            stop=stop_after_attempt(limit_attempts),
            wait=wait_exponential(multiplier=self.backoff_factor, min=1.0, max=10.0),
            retry=retry_if_exception(self._is_transient_error),
            before_sleep=self._log_retry,
            reraise=True,
        )

        # Get and check request length
        request = httpx.Request(
            method="GET", url=target_url, params=query_params, headers=request_headers
        )
        predicted_url_length = len(str(request.url))
        if (
            self.url_max_character_length
            and predicted_url_length > self.url_max_character_length
        ):
            logger.warning(
                "Request not sent: url length above max length (%d > %d "
                "characters): %s",
                predicted_url_length,
                self.url_max_character_length,
                str(request.url),
                extra={
                    "status": "WARNING",
                    "event": "http_client_url_too_long",
                    "predicted_url_length": predicted_url_length,
                    "max_url_length": self.url_max_character_length,
                    "url": str(request.url),
                },
            )
            return (None, str(request.url))

        def _execute_request() -> httpx.Response:
            resp = self.client.send(request)
            resp.raise_for_status()
            return resp

        try:
            response = retrier(_execute_request)
            logger.debug(
                "Successfully fetched URL: %s",
                str(request.url),
                extra={
                    "status": "OK",
                    "event": "http_request_success",
                    "url": str(request.url),
                    "status_code": response.status_code,
                },
            )
            return (response, str(request.url))

        except httpx.HTTPStatusError as e:
            logger.error(
                "Fatal or unresolved HTTP Error for URL %s: %s",
                target_url,
                str(e),
                extra={
                    "status": "KO",
                    "event": "http_request_fatal_status",
                    "url": target_url,
                    "status_code": e.response.status_code,
                    "error_type": type(e).__name__,
                },
            )
            raise e

        except Exception as e:
            logger.error(
                "Unexpected or unrecoverable error during request to %s: %s",
                target_url,
                str(e),
                exc_info=True,
                extra={
                    "status": "KO",
                    "event": "http_request_unexpected_crash",
                    "url": target_url,
                    "error_type": type(e).__name__,
                },
            )
            raise e

    def close(self) -> None:
        """Close the underlying synchronous HTTPX client."""
        self.client.close()
