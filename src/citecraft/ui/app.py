# src/citecraft/ui/app.py
"""Main Application window definition for the CiteCraft UI wrapper."""

import logging

import customtkinter as ctk

from citecraft.core import PipelineOptions
from citecraft.utils.config import AppConfig

logger = logging.getLogger(__name__)


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

    def _select_input_file(self) -> None:
        """Open standard file dialog to retrieve input docx filepath."""
        selected_path = ctk.filedialog.askopenfilename(
            title="Select Manuscript Document",
            filetypes=[("Word Documents", "*.docx")],
        )
        if selected_path:
            self.state.input_file_path.set(selected_path)
            logger.info("Input manuscript filepath registered: %s", selected_path)

    def _select_output_file(self) -> None:
        """Open file dialog to retrieve output destination csv path."""
        selected_path = ctk.filedialog.asksaveasfilename(
            title="Select Output CSV Location",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if selected_path:
            self.state.output_file_path.set(selected_path)
            logger.info("Output bibliography path registered: %s", selected_path)


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
