import logging
import sys
import threading
import time
from typing import Any

from manuscript_reference_lister.core import ProgressStep


class LogInterceptor(logging.Handler):
    """Handler interceptant les logs pour les insérer proprement au-dessus de la barre."""

    def __init__(self, draw_callback: Any) -> None:
        super().__init__()
        self.draw_callback = draw_callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # \r = retour chariot, \033[K = efface le reste de la ligne courante
            sys.stderr.write(f"\r\033[K{msg}\n")
            sys.stderr.flush()
            self.draw_callback()
        except Exception:
            self.handleError(record)


class ProgressBarContext:
    """Context manager responsible for the lifecycle of the CLI progress bar.

    It manages an asynchronous background thread that refreshes the console
    at a 1 Hz frequency, preventing the terminal from appearing frozen during
    long-running IO tasks (e.g., Crossref API lookups).

    If verbose_level > 0, the context remains passive and does not alter
    the standard output stream.

    New:
    Gestionnaire de contexte pour le cycle de vie de la barre de progression CLI.

    Gère un thread d'arrière-plan à 1 Hz pour éviter le gel du terminal
    pendant les requêtes réseaux (Crossref API). Active uniquement si verbose_level == 0.
    """

    def __init__(self, verbose_level: int = 0, bar_width: int = 30) -> None:
        self.verbose_level: int = verbose_level
        self.bar_width: int = bar_width
        self.is_active: bool = verbose_level == 0

        # Thread-safe communication state
        self._lock: threading.Lock = threading.Lock()
        self._state: dict[str, Any] = {
            "message": "Initializing...",
            "current_step": 0,
            "total_steps": 5,
            "running": False,
        }

        self._start_time: float = 0.0
        self._ticker_thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()

        self._old_handlers: list[logging.Handler] = []
        self._custom_handler: LogInterceptor | None = None

    def __enter__(self) -> "ProgressBarContext":
        """Starts the background execution monitoring loop if active."""
        if self.is_active:
            self._start_time = time.time()
            self._state["running"] = True
            self._stop_event.clear()

            # Configuration du détournement des logs
            root_logger = logging.getLogger()
            self._old_handlers = root_logger.handlers[:]
            for h in self._old_handlers:
                root_logger.removeHandler(h)

            self._custom_handler = LogInterceptor(draw_callback=self._draw_line)
            self._custom_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            root_logger.addHandler(self._custom_handler)

            # Lancement du thread de rafraîchissement
            self._ticker_thread = threading.Thread(
                target=self._loop_render, daemon=True
            )
            self._ticker_thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Ensures clean teardown of the thread and terminal line management."""
        if not self.is_active:
            return

        # Signal thread shutdown immediately
        with self._lock:
            self._state["running"] = False

        # Instantly wake up the thread loop to prevent test execution deadlocks
        self._stop_event.set()

        if self._ticker_thread:
            self._ticker_thread.join(timeout=1.0)

        # Restauration des handlers de logging initiaux
        root_logger = logging.getLogger()
        if self._custom_handler:
            root_logger.removeHandler(self._custom_handler)
        for h in self._old_handlers:
            root_logger.addHandler(h)

        # Evaluate final terminal status
        if exc_type is None:
            with self._lock:
                self._state["current_step"] = self._state["total_steps"]
                self._state["message"] = "Completed."
            self._draw_line()
            sys.stderr.write("\n")
        else:
            # Application crash occurred: break line instantly to keep traceback clean
            sys.stderr.write("\n")

        sys.stderr.flush()

    def update(self, step: ProgressStep) -> None:
        """Callback engine exposed directly to core.run pipeline updates.

        Thread-safe translation layer from Core structures to UI rendering.
        """
        if not self.is_active:
            return

        should_render = False
        with self._lock:
            self._state["message"] = step.message
            self._state["total_steps"] = step.total
            if step.status == "completed":
                self._state["current_step"] = step.current
                should_render = True
        # Force synchronous line redraw on step boundary resolution
        # Fix: Call draw outside of the lock context to prevent re-entrancy deadlocks
        if should_render:
            self._draw_line()

    def generate_bar_string(self, current: int, total: int, elapsed_time: float) -> str:
        """Pure operational function computing mathematical constraints of the UI."""
        percent = int((current / total) * 100) if total > 0 else 0
        filled_length = int(self.bar_width * current // total) if total > 0 else 0

        # Uses explicit cyan ANSI character blocks
        fill_char = "\033[36m█\033[0m"
        empty_char = "░"
        bar = (fill_char * filled_length) + (
            empty_char * (self.bar_width - filled_length)
        )

        if current == 0 or total == 0:
            eta_str = "--:--"
        elif current == total:
            eta_str = "00:00"
        else:
            remaining_steps = total - current
            estimated_remaining_seconds = int(
                (remaining_steps * elapsed_time) / current
            )
            eta_min, eta_sec = divmod(estimated_remaining_seconds, 60)
            eta_str = f"{eta_min:02d}:{eta_sec:02d}"

        return f"[{bar}] {percent}% (ETA: {eta_str})"

    def _loop_render(self) -> None:
        """Background worker iterating at 1 Hz frequency."""
        while not self._stop_event.is_set():
            with self._lock:
                if not self._state["running"]:
                    break
            self._draw_line()
            # Sleeps for 1s or wakes up immediately if stop_event.set() is called
            if self._stop_event.wait(timeout=1.0):
                break

    def _draw_line(self) -> None:
        """Physical renderer outputting the unified carriage-return sequence."""
        with self._lock:
            current = self._state["current_step"]
            total = self._state["total_steps"]
            msg = self._state["message"]

        elapsed = time.time() - self._start_time
        bar_component = self.generate_bar_string(current, total, elapsed)

        # Format layout matching original line configuration
        elapsed_int = int(elapsed)
        minutes, seconds = divmod(elapsed_int, 60)
        time_str = f"[{minutes:02d}:{seconds:02d}]"

        # Correction de la séquence d'effacement \r\033[K pour rester sur une ligne unique stable
        line = f"\r\033[K{time_str} {msg:<55} {bar_component}"
        sys.stderr.write(line)
        sys.stderr.flush()
