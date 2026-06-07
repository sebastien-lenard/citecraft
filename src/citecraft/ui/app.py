# src/citecraft/ui/app.py
"""Main Application window definition for the CiteCraft UI wrapper."""

import _tkinter
import contextlib
import logging
import sys
import threading

import customtkinter as ctk

from citecraft.core import PipelineOptions, run
from citecraft.utils.config import AppConfig, get_config

logger = logging.getLogger(__name__)


class TextRedirector:
    """Stream redirection layer routing print outputs safely to CTkTextbox."""

    def __init__(self, textbox: ctk.CTkTextbox) -> None:
        self.textbox = textbox

    def write(self, text: str) -> None:
        """Thread-safe write scheduler that pushes insertion to Tkinter queue."""
        if text:  # pragma: no branch
            with contextlib.suppress(_tkinter.TclError, RuntimeError, AttributeError):
                self.textbox.after(0, self._safe_write, text)

    def _safe_write(self, text: str) -> None:
        """Configure, insert, and lock console textbox in the main thread."""
        with contextlib.suppress(_tkinter.TclError, RuntimeError, AttributeError):
            self.textbox.configure(state="normal")
            self.textbox.insert("end", text)
            self.textbox.configure(state="disabled")
            self.textbox.see("end")

    def flush(self) -> None:
        """No-op flush required for sys.stdout compatibility."""


class QueueLogHandler(logging.Handler):
    """Custom logging handler that routes log records safely to the UI console."""

    def __init__(self, textbox: ctk.CTkTextbox) -> None:
        super().__init__()
        self.redirector = TextRedirector(textbox)

    def emit(self, record: logging.LogRecord) -> None:
        """Format and write the logging record safely to the redirector."""
        try:
            msg = self.format(record)
            self.redirector.write(msg + "\n")
        except Exception:  # noqa BLE001: Custom logging handlers must never allow
            # an error within the logging pipeline  to crash the application thread.
            self.handleError(record)


class UIState:
    """Holds and isolates current UI interactive variables and states."""

    def __init__(self, master: ctk.CTk) -> None:
        self.api = ctk.StringVar(value="OpenAlex")
        self.journal_title = ctk.StringVar(value="")
        self.style = ctk.StringVar(value="apa")
        self.skip_journal_update = ctk.BooleanVar(value=False)
        self.skip_work_update = ctk.BooleanVar(value=False)
        self.input_file_path = ctk.StringVar(value="No manuscript file selected")
        self.output_file_path = ctk.StringVar(value="No output CSV path selected")

    def to_pipeline_options(self, config: AppConfig) -> PipelineOptions:
        """Validate and serialize active state to strict PipelineOptions."""
        api_val = self.api.get().strip()
        style_val = self.style.get().strip()
        journal_val = self.journal_title.get().strip() or None

        in_path = self.input_file_path.get().strip()
        if in_path == "No manuscript file selected" or not in_path:
            raise ValueError("Manuscript file must be selected before processing.")

        out_path = self.output_file_path.get().strip()
        if out_path == "No output CSV path selected" or not out_path:
            raise ValueError("Output CSV destination path must be selected.")

        if not style_val:
            raise ValueError("Reference Style cannot be empty.")

        return PipelineOptions(
            api=api_val,
            input_file_path=in_path,
            input_text="",  # GUI interacts directly with local files
            output_filepath=out_path,
            config=config,
            style=style_val,
            journal_title=journal_val,
            progress_callback=None,
            skip_journal_update=self.skip_journal_update.get(),
            skip_work_update=self.skip_work_update.get(),
        )


class SidebarFrame(ctk.CTkFrame):
    """Sidebar frame containing configuration selectors and input switches."""

    def __init__(self, master: ctk.CTk, state: UIState) -> None:
        super().__init__(master, width=280, corner_radius=0)
        self.state = state
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Instantiate and position configuration input controls."""
        self.grid_columnconfigure(0, weight=1)

        # Sidebar Header Title
        title_font = ctk.CTkFont(family="Helvetica", size=20, weight="bold")
        self.lbl_title = ctk.CTkLabel(self, text="CiteCraft Settings", font=title_font)
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(20, 30), sticky="w")

        # Subsection Labels Font
        sec_font = ctk.CTkFont(family="Helvetica", size=13, weight="bold")

        # API Selection Controls
        self.lbl_api = ctk.CTkLabel(self, text="API Provider", font=sec_font)
        self.lbl_api.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")
        self.cmb_api = ctk.CTkComboBox(
            self, values=["OpenAlex", "Crossref"], variable=self.state.api
        )
        self.cmb_api.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Target Journal Controls
        self.lbl_journal = ctk.CTkLabel(
            self, text="Target Journal (Optional)", font=sec_font
        )
        self.lbl_journal.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="w")
        self.ent_journal = ctk.CTkEntry(
            self,
            placeholder_text="e.g. Geomorphology",
            textvariable=self.state.journal_title,
        )
        self.ent_journal.grid(row=4, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Reference Style Controls
        self.lbl_style = ctk.CTkLabel(self, text="Reference Style", font=sec_font)
        self.lbl_style.grid(row=5, column=0, padx=20, pady=(10, 5), sticky="w")
        self.ent_style = ctk.CTkEntry(
            self, placeholder_text="e.g. apa", textvariable=self.state.style
        )
        self.ent_style.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Boolean Skip Switches
        self.switch_skip_journal = ctk.CTkSwitch(
            self, text="Skip Journal Update", variable=self.state.skip_journal_update
        )
        self.switch_skip_journal.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.switch_skip_work = ctk.CTkSwitch(
            self, text="Skip Work Update", variable=self.state.skip_work_update
        )
        self.switch_skip_work.grid(row=8, column=0, padx=20, pady=10, sticky="w")


class MainFrame(ctk.CTkFrame):
    """Main content frame housing file picker buttons and the logging console."""

    def __init__(self, master: ctk.CTk, state: UIState) -> None:
        super().__init__(master, fg_color="transparent")
        self.state = state
        self._create_widgets()
        self._bind_events()
        self._setup_redirection()

    def _create_widgets(self) -> None:
        """Assemble main layout frames and logging textbox controls."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Logging console box takes growth

        sec_font = ctk.CTkFont(family="Helvetica", size=13, weight="bold")

        # --- Sub-frame for I/O buttons and paths ---
        self.io_frame = ctk.CTkFrame(self)
        self.io_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.io_frame.grid_columnconfigure(1, weight=1)

        # Manuscript Selection Controls
        self.btn_input = ctk.CTkButton(
            self.io_frame, text="Select Manuscript (.docx)", width=180
        )
        self.btn_input.grid(row=0, column=0, padx=15, pady=15, sticky="w")

        self.lbl_input_path = ctk.CTkLabel(
            self.io_frame, textvariable=self.state.input_file_path, anchor="w"
        )
        self.lbl_input_path.grid(row=0, column=1, padx=15, pady=15, sticky="ew")

        # Output Selection Controls
        self.btn_output = ctk.CTkButton(
            self.io_frame, text="Choose Output CSV", width=180
        )
        self.btn_output.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        self.lbl_output_path = ctk.CTkLabel(
            self.io_frame, textvariable=self.state.output_file_path, anchor="w"
        )
        self.lbl_output_path.grid(row=1, column=1, padx=15, pady=(0, 15), sticky="ew")

        # --- Console Output Terminal ---
        self.lbl_console = ctk.CTkLabel(self, text="Console Logs", font=sec_font)
        self.lbl_console.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")

        self.txt_console = ctk.CTkTextbox(self)
        self.txt_console.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="nsew")
        self.txt_console.configure(state="disabled")

        # --- Sequential Pipeline Trigger Button ---
        self.btn_run = ctk.CTkButton(
            self, text="Run Processing Pipeline", font=sec_font, height=40
        )
        self.btn_run.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")

    def _bind_events(self) -> None:
        """Bind interactive component triggers to specific internal handlers."""
        self.btn_input.configure(command=self._select_input_file)
        self.btn_output.configure(command=self._select_output_file)
        self.btn_run.configure(command=self._on_run_pipeline)

    def _setup_redirection(self) -> None:
        """Redirect python standard package logging directly to console logs."""
        # 1. Thread-safe log handler setup
        self.log_handler = QueueLogHandler(self.txt_console)
        self.log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        self.log_handler.setLevel(logging.INFO)

        # 2. Append directly to package logger boundary
        pkg_logger = logging.getLogger("citecraft")
        pkg_logger.addHandler(self.log_handler)

        # 3. Safe standard system output streams redirector hook
        self.stdout_redirector = TextRedirector(self.txt_console)
        sys.stdout = self.stdout_redirector

    def _select_input_file(self) -> None:
        """Open standard file dialog to retrieve input docx filepath."""
        selected_path = ctk.filedialog.askopenfilename(
            title="Select Manuscript Document",
            filetypes=[("Word Documents", "*.docx")],
        )
        if selected_path:  # pragma: no branch
            self.state.input_file_path.set(selected_path)
            logger.info("Input manuscript filepath registered: %s", selected_path)

    def _select_output_file(self) -> None:
        """Open file dialog to retrieve output destination csv path."""
        selected_path = ctk.filedialog.asksaveasfilename(
            title="Select Output CSV Location",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if selected_path:  # pragma: no branch
            self.state.output_file_path.set(selected_path)
            logger.info("Output bibliography path registered: %s", selected_path)

    def _on_run_pipeline(self) -> None:
        """Validate inputs, lock layout controls, and spawn background processing."""
        self._reset_validation_highlights()

        try:
            config = get_config()
            options = self.state.to_pipeline_options(config)

            self.write_console(
                f"✓ Inputs Validated.\n"
                f"  • Manuscript : {options.input_file_path}\n"
                f"  • Destination: {options.output_filepath}\n"
                f"  • Style      : {options.style}\n"
                f"  • API Engine : {options.api}\n"
                f"Starting background pipeline thread...\n"
            )

            # Disable controls to prevent concurrent pipeline launches
            self._set_controls_state("disabled")

            # Spawn synchronous backend execution in isolated daemon thread
            thread = threading.Thread(
                target=self._run_pipeline_worker, args=(options,), daemon=True
            )
            thread.start()

        except ValueError as e:
            error_msg = str(e)
            self.write_console(f"⚠ Input Validation Error: {error_msg}\n")
            self._apply_validation_highlights(error_msg)

    def _run_pipeline_worker(self, options: PipelineOptions) -> None:
        """Run synchronous bibliography process inside daemon thread context."""
        try:
            anomalous_journals, export_metadata = run(options)
            self.after(
                0,
                self._on_pipeline_completed,
                anomalous_journals,
                export_metadata,
                None,
            )
        except Exception as e:  # noqa BLE001
            # Safely marshal error back onto main UI thread
            self.after(0, self._on_pipeline_completed, [], None, e)

    def _on_pipeline_completed(
        self,
        anomalous_journals: list,
        export_metadata: object,
        error: Exception | None,
    ) -> None:
        """Re-enable visual inputs and write processing results to console."""
        self._set_controls_state("normal")

        if error:
            self.write_console(f"❌ Execution Failure: {error}\n")
            logger.error("Core processing pipeline failed.", exc_info=error)
            return

        self.write_console("✓ Processing Completed Successfully.\n")
        if export_metadata:  # pragma: no branch
            total = getattr(export_metadata, "total_rows", 0)
            path = getattr(export_metadata, "output_filepath", "")
            self.write_console(
                f"  • Total references processed: {total}\n"
                f"  • Output CSV saved to: {path}\n"
            )
        if anomalous_journals:  # pragma: no branch
            self.write_console(
                f"  • Warning: {len(anomalous_journals)} journals had ISSN conflicts"
                " or were missing. Check log files for trace details.\n"
            )

    def write_console(self, text: str) -> None:
        """Insert a logging line into the read-only console output panel."""
        self.txt_console.configure(state="normal")
        self.txt_console.insert("end", text)
        self.txt_console.configure(state="disabled")
        self.txt_console.see("end")

    def _set_controls_state(self, state: str) -> None:
        """Update interactive state configurations of all controls globally."""
        self.btn_input.configure(state=state)
        self.btn_output.configure(state=state)
        self.btn_run.configure(state=state)

        master = getattr(self, "master", None)
        sidebar = getattr(master, "sidebar", None) if master else None
        if sidebar:  # pragma: no branch
            sidebar.cmb_api.configure(state=state)
            sidebar.ent_journal.configure(state=state)
            sidebar.ent_style.configure(state=state)
            sidebar.switch_skip_journal.configure(state=state)
            sidebar.switch_skip_work.configure(state=state)

    def _apply_validation_highlights(self, error_msg: str) -> None:
        """Apply warning color schemes to inputs failing validation checks."""
        if "Manuscript file" in error_msg:
            self.btn_input.configure(border_color="red", border_width=2)
        elif "Output CSV" in error_msg:
            self.btn_output.configure(border_color="red", border_width=2)
        elif "Reference Style" in error_msg:  # pragma: no branch
            master = getattr(self, "master", None)
            sidebar = getattr(master, "sidebar", None) if master else None
            if sidebar:  # pragma: no branch
                sidebar.ent_style.configure(border_color="red")

    def _reset_validation_highlights(self) -> None:
        """Revert custom warning highlights across all config components."""
        self.btn_input.configure(border_width=0)
        self.btn_output.configure(border_width=0)
        master = getattr(self, "master", None)
        sidebar = getattr(master, "sidebar", None) if master else None
        if sidebar:  # pragma: no branch
            # Revert border_color to standard theme defaults for CTkEntry
            sidebar.ent_style.configure(border_color=["#979da2", "#565b5e"])


class CiteCraftApp(ctk.CTk):
    """Root UI window class for the CiteCraft application using CTk 5.x."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_grid()

        # Initialize Shared Local Reactive State
        self.ui_state = UIState(self)

        # Mount Sidebar Left Frame
        self.sidebar = SidebarFrame(self, self.ui_state)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Mount Main Work Frame (Column 1)
        self.main_content = MainFrame(self, self.ui_state)
        self.main_content.grid(row=0, column=1, sticky="nsew")

        logger.info("CiteCraft desktop interface structural scaffolding initialized.")

    def _setup_window(self) -> None:
        """Configure default window options and visual theme standards."""
        self.title("CiteCraft — Manuscript Bibliography Generator")
        self.geometry("1100x650")
        self.minsize(900, 500)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

    def _setup_grid(self) -> None:
        """Configure standard responsive grid weight constraints."""
        self.grid_columnconfigure(0, weight=0)  # Sidebar kept static width
        self.grid_columnconfigure(1, weight=1)  # Main pane gets flexible width
        self.grid_rowconfigure(0, weight=1)
