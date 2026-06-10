# tests/unit/test___main__.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for __main__."""

import runpy
from unittest.mock import patch


def test_main_execution() -> None:
    """Verify that running citecraft.__main__ calls the CLI entry point safely."""
    with (
        patch("sys.argv", ["citecraft"]),
        patch("citecraft.cli.cli") as mock_cli,
    ):
        runpy.run_module("citecraft.__main__", run_name="__main__")

        mock_cli.assert_called_once_with(prog_name="uv run python -m src.citecraft")
