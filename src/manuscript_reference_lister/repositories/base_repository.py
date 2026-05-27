import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from manuscript_reference_lister.network import (
    HTTPClientRegistry,
    get_http_client_registry,
)
from manuscript_reference_lister.schemas import BaseSchema
from manuscript_reference_lister.utils import (
    AppConfig,
    DataLoader,
    get_config,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BaseRepository[T: BaseSchema]:
    """Base repository delivering structured local JSON storage and schema
    enforcement."""

    def __init__(
        self,
        local_filename: str,
        model_class: type[T],
        config: AppConfig | None = None,
        registry: HTTPClientRegistry | None = None,
    ) -> None:
        self.config: AppConfig = config or get_config()
        registry = registry or get_http_client_registry()
        self.http_client_wrapper = registry.get_client("crossref")
        self.headers: dict[str, str] = {
            "User-Agent": f"ManuscriptRefLister/1.0 (mailto:"
            f"{self.config.crossref_api_email})"
        }
        self.local_filename: str = local_filename
        self._load_failed: bool = False
        self.model_class: type[T] = model_class
        self.records: list[T] = []

    def __len__(self) -> int:
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
        """Load and validate records from local storage into memory. The list of records
        of the object are set to [] if invalid."""
        path = Path(
            input_filepath
            or Path(self.config.local_repo_dir_path) / self.local_filename
        ).resolve()

        data = DataLoader(path, raise_exception=raise_exception).load_json()
        if data and isinstance(data, list):
            try:
                self.records = [self.model_class(**item) for item in data]
                self._load_failed = False
            except (TypeError, ValueError) as e:
                logger.warning(
                    "Failed validation for %s in file %s. Records set to [] for this "
                    "run. Please check the file before a rerun.",
                    self.model_class.__name__,
                    str(path),
                    extra={
                        "status": "KO",
                        "event": "repository_validation_failed",
                        "model": self.model_class.__name__,
                        "filepath": str(path),
                    },
                )
                if raise_exception:
                    raise e
                logger.debug(
                    "Validation error detail: %s",
                    str(e),
                    extra={
                        "status": "KO",
                        "event": "repository_validation_error_detail",
                    },
                )
                self.records = []
                self._load_failed = True
        else:
            self.records = []

        logger.info(
            "Loaded %d records into memory from %s",
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
        """Save records atomically to local storage using a temporary file strategy.
        Saving is done in a recovery file if previous load_all failed."""
        protected_path = Path(self.config.local_repo_dir_path) / self.local_filename
        target_path = (
            Path(output_filepath).resolve()
            if output_filepath
            else protected_path.resolve()
        )

        if self._load_failed and target_path == protected_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = (
                f"{target_path.stem}_recovered_{timestamp}{target_path.suffix}"
            )
            target_path = target_path.with_name(new_filename)

            # Update state so the repo "migrates" to the new file
            self.local_filename = new_filename
            self._load_failed = False
            logger.warning(
                "Previous load failed; diverting save to recovery file: %s",
                str(target_path),
                extra={
                    "status": "WARNING",
                    "event": "repository_save_diverted_to_recovery",
                    "recovery_filepath": str(target_path),
                },
            )

        data_to_save = [record.model_dump() for record in self.records]
        temp_path = target_path.with_suffix(".tmp")

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # Explicitly open the file with utf-8
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            temp_path.replace(target_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        logger.info(
            "Saved %d records to %s",
            len(self.records),
            str(target_path),
            extra={
                "status": "OK",
                "event": "repository_save_success",
                "record_count": len(self.records),
                "filepath": str(target_path),
            },
        )
