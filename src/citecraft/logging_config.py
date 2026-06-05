# src/citecraft/logging_config.py
import logging
import logging.config
import os
import sys
import traceback
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .utils import get_safe_dir

# Unique session identification tag
RUN_ID: str = str(uuid.uuid4())[:8]


class RunIdFilter(logging.Filter):
    """Filter that automatically injects a unique run_id into logging records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = RUN_ID  # type: ignore[attr-defined]
        return True


class ColorFormatter(logging.Formatter):
    """Custom formatter to inject ANSI escape sequences into console logs."""

    GREY = "\033[90m"
    WHITE = "\033[37m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD_RED = "\033[31;1m"
    RESET = "\033[0m"

    # Push cursor to start of line and clear current line on terminal
    CLEAR_LINE = "\r\033[K"

    LEVEL_COLORS = MappingProxyType(
        {
            logging.DEBUG: GREY,
            logging.INFO: WHITE,
            logging.WARNING: YELLOW,
            logging.ERROR: RED,
            logging.CRITICAL: BOLD_RED,
        }
    )  # immutable wrapper

    def format(self, record: logging.LogRecord) -> str:
        """Clear current terminal progress line and apply color to the output."""
        orig_name = record.name
        record.name = orig_name.rpartition(".")[-1]
        try:
            result = super().format(record)
        finally:
            record.name = orig_name  # Restore to avoid breaking other handlers

        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        return f"{self.CLEAR_LINE}{color}{result}{self.RESET}"


def get_logging_config(log_dir: Path, verbose_level: int = 0) -> dict[str, Any]:
    """Build the configuration dictionary for system loggers."""
    match verbose_level:
        case 1:
            console_level = "INFO"
        case lvl if lvl >= 2:  # noqa: PLR2004
            console_level = "DEBUG"
        case _:
            console_level = "WARNING"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "run_id_filter": {
                "()": RunIdFilter,
            }
        },
        "formatters": {
            "human": {
                "()": ColorFormatter,
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(run_id)s %(name)s %(message)s",
                "rename_fields": {"asctime": "timestamp", "levelname": "level"},
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "human",
                "level": console_level,
                "stream": "ext://sys.stderr",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "level": "DEBUG",
                "filename": str(log_dir / "app.json.log"),
                "maxBytes": 10_485_760,  # 10 MB (Clean digit separators)
                "backupCount": 5,
                "encoding": "utf8",
                "filters": ["run_id_filter"],
            },
        },
        "loggers": {
            "citecraft": {
                "handlers": (
                    ["console"]
                    if os.environ.get("ENV") == "test"
                    else ["console", "file"]
                ),  # Avoid big files in testing phase
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }


def setup_logging(verbose_level: int = 0) -> tuple[Path, Path, bool]:
    """Set up system loggers and return log directory path, original intended path,
    and a boolean = True if it had to resort to a temp directory."""
    log_dir, intended_dir, is_fallback = get_safe_dir("logs")

    try:
        config = get_logging_config(log_dir, verbose_level=verbose_level)
        logging.config.dictConfig(config)
    except (ValueError, KeyError, ImportError, OSError) as e:
        # Fallback to standard error console if directory is locked or unwritable
        print(
            f"CRITICAL: Failed to initialize logging system configuration: {e}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    return log_dir, intended_dir, is_fallback
