# src/citecraft/storage/db.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database management utilities for converting and saving Pydantic records."""

import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from .db_client import DbClient

logger = logging.getLogger(__name__)


def _is_collection_type(type_annotation: object) -> bool:
    """Determine if a type annotation represents a list, dict, or set."""
    if type_annotation is None:
        return False
    origin = get_origin(type_annotation)
    if origin in (list, dict, set):
        return True
    if origin in (Union, UnionType):
        return any(_is_collection_type(arg) for arg in get_args(type_annotation))

    return isinstance(type_annotation, type) and issubclass(
        type_annotation,
        list | dict | set,
    )


def _get_sqlite_type(type_annotation: object) -> str:
    """Map Python and Pydantic types to SQLite equivalents."""
    if type_annotation is None:
        return "TEXT"

    origin = get_origin(type_annotation)
    if origin in (Union, UnionType):
        args = [arg for arg in get_args(type_annotation) if arg is not type(None)]
        return _get_sqlite_type(args[0]) if args else "TEXT"

    result = "TEXT"
    if isinstance(type_annotation, type):
        if issubclass(type_annotation, bool | int):
            result = "INTEGER"
        elif issubclass(type_annotation, float):
            result = "REAL"

    return result


def create_table_for_model(
    conn: sqlite3.Connection,
    table_name: str,
    model_class: type[BaseModel],
) -> None:
    """Create a table dynamically based on Pydantic model fields."""
    column_definitions = [
        (name, _get_sqlite_type(field.annotation))
        for name, field in model_class.model_fields.items()
    ]

    DbClient.safe_create_table(conn, table_name, column_definitions)


def serialize_model(record: BaseModel) -> dict[str, Any]:
    """Serialize model fields, converting lists, dicts, and sets to JSON strings."""
    data = record.model_dump()
    for key, val in data.items():
        if isinstance(val, list | dict | set):
            data[key] = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, Path):
            data[key] = str(val)
    return data


def deserialize_row[T: BaseModel](row_dict: dict[str, Any], model_class: type[T]) -> T:
    """Convert raw database row data into the target Pydantic model."""
    deserialized: dict[str, Any] = {}
    for key, val in row_dict.items():
        field = model_class.model_fields.get(key)
        if field is None:
            continue

        if val is None:
            if not field.is_required():
                continue
            deserialized[key] = None
        elif _is_collection_type(field.annotation) and isinstance(val, str):
            try:
                deserialized[key] = json.loads(val)
            except json.JSONDecodeError:
                deserialized[key] = val
        else:
            deserialized[key] = val
    return model_class(**deserialized)


def save_records[T: BaseModel](
    db_path: Path,
    table_name: str,
    records: list[T],
    model_class: type[T],
) -> None:
    """Atomically save records to the database within a transaction."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            with conn:
                conn.row_factory = sqlite3.Row
                create_table_for_model(conn, table_name, model_class)
                DbClient.safe_execute(conn, "DELETE FROM {table_name};", table_name)

                if records:
                    fields = list(model_class.model_fields.keys())
                    rows_to_insert = [
                        tuple(serialize_model(rec)[field] for field in fields)
                        for rec in records
                    ]
                    DbClient.safe_execute_many(conn, table_name, fields, rows_to_insert)

        except sqlite3.Error:
            logger.exception(
                "Transaction failed for table %s. State rolled back.",
                table_name,
                extra={"table_name": table_name},
            )
            raise


def load_records[T: BaseModel](
    db_path: Path,
    table_name: str,
    model_class: type[T],
) -> list[T]:
    """Retrieve all records for a given model from the SQLite database."""
    if not db_path.exists():
        return []

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if not DbClient.table_exists(conn, table_name):
            return []
        rows = DbClient.safe_fetch_all(conn, "SELECT * FROM {table_name};", table_name)
        return [deserialize_row(dict(row), model_class) for row in rows]


def archive_database_cache(db_path: Path) -> Path | None:
    """Safely archive local database cache by renaming it with timestamp suffix."""
    if not db_path.is_file():
        logger.warning(
            "Database cache file not found for archiving: %s",
            str(db_path),
            extra={
                "event": "db_file_not_found",
                "db_path": str(db_path),
            },
        )
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.name}.bak_{timestamp}"
    backup_path = db_path.with_name(backup_name)

    try:
        db_path.rename(backup_path)
        logger.info(
            "Database cache archived: %s to %s",
            db_path.name,
            backup_name,
            extra={
                "event": "db_archived",
                "db_path": db_path.name,
                "db_backup_path": backup_name,
            },
        )

    except OSError as e:
        logger.exception(
            "Failed to archive database cache file %s",
            str(db_path),
            extra={
                "event": "db_not_archived",
                "db_path": str(db_path),
                "error": str(e),
            },
        )
        raise
    else:
        return backup_path
