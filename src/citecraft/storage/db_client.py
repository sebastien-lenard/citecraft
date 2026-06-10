# src/citecraft/storage/db_client.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database client module providing injection-safe, dynamic SQL operations."""

import sqlite3
from collections.abc import Iterable


class DbClient:
    """Provides secure, injection-safe database transactional operations."""

    @classmethod
    def quote_identifier(cls, identifier: str) -> str:
        """Strictly escape a database identifier (table or column name)."""
        return f'"{identifier.replace('"', '""')}"'

    @classmethod
    def safe_execute(
        cls,
        conn: sqlite3.Connection,
        sql_template: str,
        table_name: str,
        *args: object,
        **kwargs: object,
    ) -> sqlite3.Cursor:
        """Format a table identifier safely into a SQL template and executes it."""
        safe_table = cls.quote_identifier(table_name)

        # 1. Safely construct the query string
        query = sql_template.format(table_name=safe_table)

        # 2. Unify the query parameters to satisfy the Type Checker
        # sqlite3 needs either a sequence (args) or a dict (kwargs)
        parameters: tuple[object, ...] | dict[str, object] = kwargs or args

        # 3. Pass the parameters object directly
        return conn.execute(query, parameters)

    @classmethod
    def safe_execute_many(
        cls,
        conn: sqlite3.Connection,
        table_name: str,
        fields: list[str],
        rows_to_insert: Iterable[tuple[object, ...]],
    ) -> sqlite3.Cursor:
        """Safely builds an INSERT template and runs executemany."""
        safe_table = cls.quote_identifier(table_name)
        safe_fields = [cls.quote_identifier(field) for field in fields]
        placeholders = ", ".join("?" for _ in fields)

        # All identifiers are safely escaped prior to string generation
        query = (
            f"INSERT INTO {safe_table} ({', '.join(safe_fields)}) "
            f"VALUES ({placeholders});"
        )
        return conn.executemany(query, rows_to_insert)

    @classmethod
    def safe_create_table(
        cls,
        conn: sqlite3.Connection,
        table_name: str,
        column_definitions: list[tuple[str, str]],
    ) -> sqlite3.Cursor:
        """Safely builds a DDL CREATE TABLE statement with type validation."""
        safe_table = cls.quote_identifier(table_name)
        columns_sql = []

        for name, sql_type in column_definitions:
            # Safely allow alphanumeric characters, spaces, and size descriptors
            if not all(c.isalnum() or c.isspace() or c in "()," for c in sql_type):
                err_msg = f"Unsafe SQL type definition detected: {sql_type}"
                raise ValueError(err_msg)

            safe_col_name = cls.quote_identifier(name)
            columns_sql.append(f"{safe_col_name} {sql_type}")

        query = f"CREATE TABLE IF NOT EXISTS {safe_table} ({', '.join(columns_sql)});"
        return conn.execute(query)

    @classmethod
    def safe_fetch_all(
        cls,
        conn: sqlite3.Connection,
        sql_template: str,
        table_name: str,
        *args: object,
        **kwargs: object,
    ) -> list[sqlite3.Row]:
        """Format table identifier safely into a read query and fetches all rows."""
        safe_table = cls.quote_identifier(table_name)
        query = sql_template.format(table_name=safe_table)
        parameters: tuple[object, ...] | dict[str, object] = kwargs or args
        cursor = conn.execute(query, parameters)
        return cursor.fetchall()

    @classmethod
    def table_exists(cls, conn: sqlite3.Connection, table_name: str) -> bool:
        """Use a parameterized schema query to safely check if a table exists."""
        cursor = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        return cursor.fetchone() is not None
