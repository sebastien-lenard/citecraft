# src/storage/db.py
import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _is_collection_type(type_annotation: Any) -> bool:
    """Determine if a type annotation represents a list, dict, or set."""
    if type_annotation is None:
        return False
    origin = get_origin(type_annotation)
    if origin in (list, dict, set):
        return True
    if origin in (Union, UnionType):
        return any(_is_collection_type(arg) for arg in get_args(type_annotation))
    try:
        if issubclass(type_annotation, (list, dict, set)):
            return True
    except TypeError:
        pass
    return False


def _get_sqlite_type(type_annotation: Any) -> str:
    """Map Python and Pydantic types to SQLite equivalents."""
    if type_annotation is None:
        return "TEXT"
    origin = get_origin(type_annotation)
    if origin in (Union, UnionType):
        args = [arg for arg in get_args(type_annotation) if arg is not type(None)]
        if args:
            return _get_sqlite_type(args[0])
        return "TEXT"
    try:
        if issubclass(type_annotation, bool):
            return "INTEGER"
        if issubclass(type_annotation, int):
            return "INTEGER"
        if issubclass(type_annotation, float):
            return "REAL"
    except TypeError:
        pass
    return "TEXT"


def create_table_for_model(
    conn: sqlite3.Connection, table_name: str, model_class: type[BaseModel]
) -> None:
    """Create a table dynamically based on Pydantic model fields."""
    columns = []
    for name, field in model_class.model_fields.items():
        sql_type = _get_sqlite_type(field.annotation)
        columns.append(f'"{name}" {sql_type}')

    query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)});"
    conn.execute(query)


def serialize_model(record: BaseModel) -> dict[str, Any]:
    """Serialize model fields, converting lists, dicts, and sets to JSON strings."""
    data = record.model_dump()
    for key, val in data.items():
        if isinstance(val, (list, dict, set)):
            data[key] = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, Path):
            data[key] = str(val)
    return data


def deserialize_row[T: BaseModel](row_dict: dict[str, Any], model_class: type[T]) -> T:
    """Convert raw database row data into the target Pydantic model."""
    deserialized: dict[str, Any] = {}
    for key, val in row_dict.items():
        field = model_class.model_fields.get(key)
        if field is not None and val is not None:
            if _is_collection_type(field.annotation):
                if isinstance(val, str):
                    try:
                        deserialized[key] = json.loads(val)
                    except json.JSONDecodeError:
                        deserialized[key] = val
                else:
                    deserialized[key] = val
            else:
                deserialized[key] = val
        else:
            deserialized[key] = val
    return model_class(**deserialized)


def save_records[T: BaseModel](
    db_path: Path, table_name: str, records: list[T], model_class: type[T]
) -> None:
    """Atomically save records to the database within a transaction."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            with conn:
                conn.row_factory = sqlite3.Row
                create_table_for_model(conn, table_name, model_class)

                conn.execute(f"DELETE FROM {table_name};")
                if records:
                    fields = list(model_class.model_fields.keys())
                    escaped_fields = [f'"{field}"' for field in fields]
                    placeholders = ", ".join("?" for _ in fields)
                    query = (
                        f"INSERT INTO {table_name} ({', '.join(escaped_fields)}) "
                        f"VALUES ({placeholders});"
                    )

                    rows_to_insert = []
                    for rec in records:
                        serialized = serialize_model(rec)
                        rows_to_insert.append(
                            tuple(serialized[field] for field in fields)
                        )

                    conn.executemany(query, rows_to_insert)

        except sqlite3.Error as e:
            logger.error(
                "Transaction failed for table %s. State rolled back: %s",
                table_name,
                str(e),
                exc_info=True,
            )
            raise e


def load_records[T: BaseModel](
    db_path: Path, table_name: str, model_class: type[T]
) -> list[T]:
    """Retrieve all records for a given model from the SQLite database."""
    if not db_path.exists():
        return []

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        if not cursor.fetchone():
            return []

        cursor = conn.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()

        return [deserialize_row(dict(row), model_class) for row in rows]


def archive_database_cache(db_path: Path) -> Path | None:
    """Safely archive the local database cache by renaming it with a timestamp
    suffix."""
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        return backup_path
    except OSError as e:
        logger.error(
            "Failed to archive database cache file %s: %s",
            str(db_path),
            str(e),
            exc_info=True,
            extra={
                "event": "db_not_archived",
                "db_path": str(db_path),
                "error": str(e),
            },
        )
        raise e
