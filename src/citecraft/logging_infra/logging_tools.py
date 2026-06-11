# src/citecraft/logging_infra/logging_tools.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""A toolbox to assist logging."""

import logging
import time

from citecraft.utils import (
    AppConfig,
)

logger = logging.getLogger(__name__)


class LoggingTools:
    """A toolbox to assist logging."""

    @staticmethod
    def log_heartbeat_if_needed(
        processed: int,
        total: int,
        last_time: float,
        config: AppConfig,
    ) -> float:
        """Log batch resolution progress every 10 seconds of processing time."""
        current_time = time.time()
        if (
            current_time - last_time
            > config.default_logging_frequency_for_batch_updates
        ):
            remaining = total - processed
            logger.info(
                "Batch update status: %d updates remaining out of %d",
                remaining,
                total,
                extra={
                    "status": "OK",
                    "event": "batch_update_heartbeat",
                    "remaining_count": remaining,
                    "total_count": total,
                },
            )
            return current_time
        return last_time
