# tests/unit/logging_infra/test_logging_tools.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the LoggingTools logging assistant helper class."""

import logging
import time

import pytest

from citecraft.logging_infra.logging_tools import LoggingTools
from citecraft.utils import AppConfig


def test_log_heartbeat_if_needed_triggers_log(
    test_config: AppConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify heartbeat logs correctly and updates tracking timestamp when overdue."""
    test_config = test_config.model_copy(
        update={"default_logging_frequency_for_batch_updates": 5.0},
    )
    last_time = time.time() - 10.0  # Elapse 10s (exceeds 5.0s threshold)

    with caplog.at_level(logging.INFO):
        new_time = LoggingTools.log_heartbeat_if_needed(
            processed=2,
            total=10,
            last_time=last_time,
            config=test_config,
        )

    # Assert time updated to current run time
    assert new_time > last_time
    assert abs(new_time - time.time()) < 0.2

    # Assert logger.info properties
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "INFO"
    assert "Batch update status: 8 updates remaining out of 10" in record.message

    # Assert extra properties passed to logger
    assert getattr(record, "status", None) == "OK"
    assert getattr(record, "event", None) == "batch_update_heartbeat"
    assert getattr(record, "remaining_count", None) == 8
    assert getattr(record, "total_count", None) == 10


def test_log_heartbeat_if_needed_skips_log(
    test_config: AppConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check returns unmodified last_time and skips logging when not overdue."""
    test_config = test_config.model_copy(
        update={"default_logging_frequency_for_batch_updates": 10.0},
    )
    last_time = time.time() - 5.0  # Elapse 5s (falls below 10.0s threshold)

    with caplog.at_level(logging.INFO):
        new_time = LoggingTools.log_heartbeat_if_needed(
            processed=2,
            total=10,
            last_time=last_time,
            config=test_config,
        )

    # Return must match initial reference timestamp
    assert new_time == last_time
    # Logging engine should remain untouched
    assert len(caplog.records) == 0
