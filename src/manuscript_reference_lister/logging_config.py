import logging.config
import os
import sys
import tempfile
import uuid
from pathlib import Path
from types import MappingProxyType

from dotenv import dotenv_values

# Unique run_id valid for the session CLI
RUN_ID = str(uuid.uuid4())[:8]


class RunIdFilter(logging.Filter):
    """Injects session run_id automatically in log."""

    def filter(self, record):
        record.run_id = RUN_ID
        return True


class ColorFormatter(logging.Formatter):
    """Custom formatter to inject ANSI escape sequences into console logs."""

    GREY = "\033[90m"
    WHITE = "\033[37m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD_RED = "\033[31;1m"
    RESET = "\033[0m"

    LEVEL_COLORS = MappingProxyType(
        {
            logging.DEBUG: GREY,
            logging.INFO: WHITE,
            logging.WARNING: YELLOW,
            logging.ERROR: RED,
            logging.CRITICAL: BOLD_RED,
        }
    )  # immutable wrapper

    def format(self, record):
        """Generates the log string normally, then wraps the entire line with the
        appropriate level color.
        """
        result = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        return f"{color}{result}{self.RESET}"


def get_safe_log_dir() -> Path:
    """Get environment LOG_DIR_PATH (may be overriden by conftest.py) or shifts to OS
    temporary directory subfolder (Windows/Linux/macOS)."""
    try:
        env_val = os.environ.get("LOG_DIR_PATH")
        if not env_val:
            env_vars = dotenv_values(".env")
            env_val = env_vars.get("LOG_DIR_PATH")
        if env_val:
            return Path(env_val.strip('"').strip("'"))
    except Exception:
        pass

    # Fallback solution C:\Users\Nom\AppData\Local\Temp\manuscript-reference-lister
    # on Windows or /tmp/manuscript-reference-lister on Linux/MacOS
    return Path(tempfile.gettempdir()) / "manuscript-reference-lister"


def get_logging_config(log_dir: Path, verbose_level: int = 0) -> dict:
    """Log configuration dictionary."""
    console_level = "WARNING"
    if verbose_level == 1:
        console_level = "INFO"
    elif verbose_level >= 2:
        console_level = "DEBUG"

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
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 5,
                "encoding": "utf8",
                "filters": ["run_id_filter"],
            },
        },
        "loggers": {
            "manuscript_reference_lister": {
                "handlers": ["console"]
                if os.environ.get("ENV") == "test"
                else ["console", "file"],
                # Avoid big files in testing phase
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }


def setup_logging(verbose_level: int = 0) -> Path:
    """Set up global log system and returns log path."""
    log_dir = get_safe_log_dir()

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        config = get_logging_config(log_dir, verbose_level=verbose_level)
        logging.config.dictConfig(config)
    except Exception as e:
        # Fallback to stderr if locked disk
        print(
            f"CRITICAL: Failed to initialize log directory at {log_dir}: {e}",
            file=sys.stderr,
        )
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    return log_dir
