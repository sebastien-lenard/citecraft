# tests/unit/ui/test_progress_bar_context.py
# SPDX-FileCopyrightText: 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests validating CLI progress bar layout formatting, lifecycle, and logs."""

import io
import logging
import sys
import time
from unittest.mock import patch

import pytest

from citecraft.core import ProgressStep
from citecraft.ui.progress_bar_context import LogInterceptor, ProgressBarContext


def test_generate_bar_string_initial_state() -> None:
    """Verify bar string formatting when no steps have been processed."""
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)
    # current = 0, total = 4, elapsed = 5.0
    bar_str = ctx.generate_bar_string(0, 4, 5.0)

    assert "░" * 10 in bar_str
    assert "0%" in bar_str
    assert "ETA: --:--" in bar_str


def test_generate_bar_string_zero_elapsed_time() -> None:
    """Verify that elapsed time at zero does not trigger ZeroDivisionError."""
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)
    # Boundary: 0 elapsed time, 0 step achieved
    bar_str_initial = ctx.generate_bar_string(0, 4, 0.0)
    assert "ETA: --:--" in bar_str_initial

    # Boundary: step achieved but 0 elapsed time
    bar_str_progress = ctx.generate_bar_string(2, 4, 0.0)
    assert "ETA: 00:00" in bar_str_progress


def test_generate_bar_string_mid_progress() -> None:
    """Verify ETA calculation and fill ratio at progress midpoint."""
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)
    # 2 out of 4 steps done in 10 seconds -> 5 seconds per step average.
    # 2 steps remaining * 5s = 10s remaining -> ETA: 00:10
    bar_str = ctx.generate_bar_string(2, 4, 10.0)

    # 50% fill: 5 filled chars, 5 empty chars
    expected_fill = "\033[36m█\033[0m" * 5 + "░" * 5
    assert expected_fill in bar_str
    assert "50%" in bar_str
    assert "ETA: 00:10" in bar_str


def test_generate_bar_string_completed_state() -> None:
    """Verify that completing all steps forces ETA to zero."""
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)
    bar_str = ctx.generate_bar_string(4, 4, 15.0)

    assert "\033[36m█\033[0m" * 10 in bar_str
    assert "100%" in bar_str
    assert "ETA: 00:00" in bar_str


def test_progress_bar_passive_mode_when_verbose() -> None:
    """Ensure context remains completely silent if verbose level is activated."""
    with ProgressBarContext(verbose_level=1) as ctx:
        assert ctx.is_active is False
        assert ctx._ticker_thread is None

        # Callbacks should execute as no-ops safely
        step = ProgressStep(
            step_name="parsing",
            current=1,
            total=4,
            message="Test",
            status="started",
        )
        ctx.update(step)
        assert ctx._state["current_step"] == 0  # State unchanged


def test_progress_lifecycle_and_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test standard execution lifecycle rendering on sys.stderr."""
    fake_stderr = io.StringIO()
    # Replace sys.stderr safely during this test execution
    monkeypatch.setattr(sys, "stderr", fake_stderr)
    # We use a passive manual execution by mocking or controlling time to avoid 1Hz
    # sleep race conditions
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)

    with ctx:
        # Simulate core pipeline calling the update handler
        ctx.update(
            ProgressStep(
                step_name="parsing",
                current=1,
                total=4,
                message="Parsing documents",
                status="completed",
            ),
        )
        # Leave brief window for background thread to execute one loop cleanly
        time.sleep(0.05)

    output = fake_stderr.getvalue()

    # Assert specific visual structures match our designed layout
    assert "Initializing..." in output
    assert "Parsing documents" in output
    assert "25%" in output
    assert "Completed." in output


def test_progress_lifecycle_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that a pipeline crash forces a newline without printing 'Completed.'."""
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)
    ctx = ProgressBarContext(verbose_level=0, bar_width=10)

    # Converting to PT012 puts the test in fail.
    with pytest.raises(ValueError, match="Pipeline Failure"), ctx:  # noqa: PT012
        ctx.update(
            ProgressStep(
                step_name="parsing",
                current=0,
                total=4,
                message="Crashing step",
                status="started",
            ),
        )
        err_msg = "Pipeline Failure"
        raise ValueError(err_msg)

    output = fake_stderr.getvalue()
    assert "Completed." not in output
    # Ends with a raw newline to clear the line for the incoming traceback
    assert output.endswith("\n")


def test_log_clears_progress_bar_line(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that logging correctly erase progress bar lines before emitting logs."""
    # 1. Setup local logging infrastructure connected to root for context interception
    test_logger = logging.getLogger("citecraft.integ_ui")
    test_logger.setLevel(logging.WARNING)
    test_logger.propagate = (
        True  # Must propagate to root so ProgressBarContext can intercept it
    )

    try:
        # 2. Emulate an active progress UI layout state
        ctx = ProgressBarContext(verbose_level=0, bar_width=10)

        with ctx:
            # Force an explicit line draw to establish the terminal state
            # "Initializing..."
            ctx._draw_line()

            # Emit a warning log midway through execution
            test_logger.warning("Network timeout encountered, retrying...")

            # Draw line again to mimic the next 1Hz tick iteration
            ctx._draw_line()

        captured = capsys.readouterr()
        err_output = captured.err

        # 3. Assert structural integrity of the stream sequence
        # The output must contain the clear line carriage return token before the log
        # Note: In Option B, LogInterceptor applies formatting or the context redraws.
        assert "Network timeout encountered, retrying..." in err_output

        # Verify ANSI erase sequence
        # Log mustn't overwrite remaining progressbar
        assert "\r\033[K" in err_output or "\r\x1b[K" in err_output

        # Verify the progress bar successfully reprinted its states during the cycle
        assert "Initializing..." in err_output
        assert "Completed." in err_output

    finally:
        # Ensure clean state for subsequent tests
        test_logger.propagate = False


def test_logging_handlers_are_cleaned_on_exception() -> None:
    """Verify that ProgressBarContext removes handlers during crashes."""
    root_logger = logging.getLogger()
    initial_handlers = list(root_logger.handlers)

    ctx = ProgressBarContext(verbose_level=0, bar_width=10)

    with ctx:
        assert any(
            x.__class__.__name__ == "LogInterceptor" for x in root_logger.handlers
        )
        err_msg = "Forced pipeline crash"
        with pytest.raises(RuntimeError, match="Forced pipeline crash"):
            raise RuntimeError(err_msg)

    # After-crash verification: initial state must be restored.
    assert root_logger.handlers == initial_handlers


def test_log_interceptor_emit_exception_handled() -> None:
    """Verify LogInterceptor safely recovers when standard streams are locked."""
    interceptor = LogInterceptor(draw_callback=lambda: None)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="path",
        lineno=10,
        msg="log message content",
        args=(),
        exc_info=None,
    )

    with (
        patch("sys.stderr.write", side_effect=RuntimeError("Stream blocked")),
        patch.object(interceptor, "handleError") as mock_handle_error,
    ):
        interceptor.emit(record)
        mock_handle_error.assert_called_once_with(record)


def test_exit_with_falsy_handlers_and_threads() -> None:
    """Verify __exit__ clears context even if handles or threads are None."""
    ctx = ProgressBarContext(verbose_level=0)
    ctx.is_active = True
    ctx._ticker_thread = None
    ctx._custom_handler = None

    # This call should finalize cleanly and execute zero-ops on falsy values
    ctx.__exit__(None, None, None)


def test_loop_render_stops_immediately_if_stop_event_set() -> None:
    """Verify loop exits instantly if the shutdown signal was pre-configured."""
    ctx = ProgressBarContext(verbose_level=0)
    ctx._stop_event.set()

    with patch.object(ctx, "_draw_line") as mock_draw:
        ctx._loop_render()
        mock_draw.assert_not_called()


def test_loop_render_breaks_if_not_running() -> None:
    """Verify background task breaks when context running state is deactivated."""
    ctx = ProgressBarContext(verbose_level=0)
    ctx._state["running"] = False
    ctx._stop_event.clear()

    with patch.object(ctx, "_draw_line") as mock_draw:
        ctx._loop_render()
        mock_draw.assert_not_called()


def test_loop_render_continues_on_wait_timeout() -> None:
    """Verify background task processes next loop iteration if wait timeout expires."""
    ctx = ProgressBarContext(verbose_level=0)
    ctx._state["running"] = True
    ctx._stop_event.clear()

    call_count = 0

    def mock_draw() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            # Safely trigger loop break on next iteration
            ctx._state["running"] = False

    with (
        patch.object(ctx, "_draw_line", side_effect=mock_draw),
        patch.object(ctx._stop_event, "wait", return_value=False) as mock_wait,
    ):
        ctx._loop_render()
        assert call_count == 2
        mock_wait.assert_called()
