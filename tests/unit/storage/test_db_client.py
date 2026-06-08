# tests/unit/storage/test_db_client.py
"""Unit tests for validation limits and safe execution methods in DbClient."""

import sqlite3
from collections.abc import Generator
from contextlib import closing

import pytest

from citecraft.storage.db_client import DbClient


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    """Provide an isolated, in-memory SQLite database connection."""
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def test_quote_identifier_escaping() -> None:
    """Verify that identifiers are strictly quoted and double-quotes are escaped."""
    assert DbClient.quote_identifier("my_table") == '"my_table"'
    assert DbClient.quote_identifier('my"table') == '"my""table"'


def test_safe_execute_with_args(conn: sqlite3.Connection) -> None:
    """Verify safe_execute formats table identifiers and parses args."""
    conn.execute("CREATE TABLE test_table (id INTEGER, val TEXT);")
    DbClient.safe_execute(
        conn,
        "INSERT INTO {table_name} (id, val) VALUES (?, ?);",
        "test_table",
        1,
        "first_value",
    )

    row = conn.execute("SELECT * FROM test_table;").fetchone()
    assert row["id"] == 1
    assert row["val"] == "first_value"


def test_safe_execute_with_kwargs(conn: sqlite3.Connection) -> None:
    """Verify safe_execute formats table identifiers and parses kwargs."""
    conn.execute("CREATE TABLE test_table (id INTEGER, val TEXT);")
    DbClient.safe_execute(
        conn,
        "INSERT INTO {table_name} (id, val) VALUES (:id, :val);",
        "test_table",
        id=2,
        val="second_value",
    )

    row = conn.execute("SELECT * FROM test_table WHERE id = 2;").fetchone()
    assert row["id"] == 2
    assert row["val"] == "second_value"


def test_safe_execute_many(conn: sqlite3.Connection) -> None:
    """Verify batch inserts write all rows with correctly escaped columns."""
    conn.execute("CREATE TABLE test_batch (id INTEGER, val TEXT);")
    rows = [(1, "A"), (2, "B"), (3, "C")]

    DbClient.safe_execute_many(conn, "test_batch", ["id", "val"], rows)

    results = conn.execute("SELECT * FROM test_batch ORDER BY id ASC;").fetchall()
    assert len(results) == 3
    assert results[0]["val"] == "A"
    assert results[2]["val"] == "C"


def test_safe_create_table_validation(conn: sqlite3.Connection) -> None:
    """Verify successful DDL creation and validation boundaries for types."""
    # 1. Success with standard size-delimited and nested types
    columns = [
        ("id", "INTEGER"),
        ("name", "VARCHAR(255)"),
        ("weight", "DECIMAL(10,2)"),
    ]
    DbClient.safe_create_table(conn, "valid_table", columns)
    assert DbClient.table_exists(conn, "valid_table") is True

    # 2. Failure with illegal characters violating DDL injection blocks
    bad_columns = [("id", "INTEGER; DROP TABLE valid_table;")]
    with pytest.raises(ValueError, match="Unsafe SQL type definition detected"):
        DbClient.safe_create_table(conn, "invalid_table", bad_columns)


def test_safe_fetch_all_scenarios(conn: sqlite3.Connection) -> None:
    """Verify that multiple records are fetched safely with parameter mappings."""
    conn.execute("CREATE TABLE test_fetch (id INTEGER, val TEXT);")
    conn.execute("INSERT INTO test_fetch (id, val) VALUES (10, 'X'), (20, 'Y');")

    # Fetch using positional parameters
    res_args = DbClient.safe_fetch_all(
        conn,
        "SELECT * FROM {table_name} WHERE id > ?;",
        "test_fetch",
        5,
    )
    assert len(res_args) == 2

    # Fetch using keyword parameters
    res_kwargs = DbClient.safe_fetch_all(
        conn,
        "SELECT * FROM {table_name} WHERE val = :val_name;",
        "test_fetch",
        val_name="Y",
    )
    assert len(res_kwargs) == 1
    assert res_kwargs[0]["id"] == 20


def test_table_exists_boundaries(conn: sqlite3.Connection) -> None:
    """Verify table checks for existent and nonexistent names."""
    conn.execute("CREATE TABLE existing_table (id INTEGER);")
    assert DbClient.table_exists(conn, "existing_table") is True
    assert DbClient.table_exists(conn, "absent_table") is False
