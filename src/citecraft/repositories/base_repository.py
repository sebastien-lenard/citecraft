# src/citecraft/repositories/base_repository.py
"""Base database repository implementing storage operations and schema enforcement."""

import logging
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from citecraft.network import (
    HTTPClientRegistry,
    get_http_client_registry,
)
from citecraft.schemas import BaseSchema
from citecraft.storage.db import load_records, save_records
from citecraft.utils import (
    AppConfig,
    get_config,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BaseRepository[T: BaseSchema]:
    """Base repository delivering local storage and schema enforcement."""

    def __init__(
        self,
        local_filename: str,
        model_class: type[T],
        config: AppConfig | None = None,
        api: str = "crossref",
        registry: HTTPClientRegistry | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper = registry.get_client(api)
        self.headers: dict[str, str] = {
            "User-Agent": f"ManuscriptRefLister/1.0 (mailto:"
            f"{self.http_client_wrapper.email})",
        }
        self.local_filename: str = local_filename
        self.table_name: str = Path(local_filename).stem
        self._load_failed: bool = False
        self.model_class: type[T] = model_class
        self.records: list[T] = []

    def __len__(self) -> int:
        """Return the number of records currently loaded in memory."""
        return len(self.records)

    def deduplicate(self) -> None:
        """Remove duplicate records in-place based on their identity keys."""
        seen = set()
        unique_records = []

        for record in self.records:
            key = record.identity_key
            if key not in seen:
                seen.add(key)
                unique_records.append(record)

        self.records = unique_records

    def load_all(
        self,
        input_filepath: str | Path | None = None,
        *,
        raise_exception: bool = False,
    ) -> None:
        """Load and validate records into memory.

        The list of records of the object are set to [] if invalid.
        """
        path = Path(input_filepath or self.config.db_filepath).resolve()

        try:
            self.records = load_records(path, self.table_name, self.model_class)
            self._load_failed = False
        except (sqlite3.Error, TypeError, ValueError):
            logger.warning(
                "Failed validation or database corrupted for %s in SQLite file %s. "
                "Triggering database recovery and backup.",
                self.model_class.__name__,
                str(path),
                extra={
                    "status": "KO",
                    "event": "repository_validation_failed",
                    "model": self.model_class.__name__,
                    "filepath": str(path),
                },
            )

            if path.is_file():
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{path.stem}_corrupted_{timestamp}{path.suffix}"
                backup_path = path.with_name(backup_filename)
                try:
                    path.rename(backup_path)
                    logger.warning(
                        "Corrupted database backed up to: %s",
                        str(backup_path),
                        extra={"event": "database_corrupted_backup_created"},
                    )
                except OSError:
                    logger.exception(
                        "Failed to back up corrupted database",
                    )
                    with suppress(OSError):
                        path.unlink(missing_ok=True)

            self.records = []
            self._load_failed = True
            if raise_exception:
                raise

        logger.info(
            "Loaded %d records into memory from SQLite %s",
            len(self.records),
            str(path),
            extra={
                "status": "OK",
                "event": "repository_load_success",
                "record_count": len(self.records),
                "filepath": str(path),
            },
        )

    def save_all(self, output_filepath: str | Path | None = None) -> None:
        """Save records atomically to SQLite storage within a transaction."""
        target_path = Path(output_filepath or self.config.db_filepath).resolve()

        try:
            save_records(target_path, self.table_name, self.records, self.model_class)
            self._load_failed = False
        except (sqlite3.Error, OSError):
            logger.exception(
                "Failed to save records to SQLite at %s",
                str(target_path),
            )
            raise

        logger.info(
            "Saved %d records to SQLite %s",
            len(self.records),
            str(target_path),
            extra={
                "status": "OK",
                "event": "repository_save_success",
                "record_count": len(self.records),
                "filepath": str(target_path),
            },
        )
