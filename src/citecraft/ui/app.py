# src/citecraft/ui/app.py
"""Main Application window definition for the CiteCraft UI wrapper."""

import logging

import customtkinter as ctk

logger = logging.getLogger(__name__)


class SidebarFrame(ctk.CTkFrame):
    """Sidebar frame containing configuration selectors and input switches."""

    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master, width=280, corner_radius=0)
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
        self.cmb_api = ctk.CTkComboBox(self, values=["OpenAlex", "Crossref"])
        self.cmb_api.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Target Journal Controls
        self.lbl_journal = ctk.CTkLabel(
            self, text="Target Journal (Optional)", font=sec_font
        )
        self.lbl_journal.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="w")
        self.ent_journal = ctk.CTkEntry(self, placeholder_text="e.g. Geomorphology")
        self.ent_journal.grid(row=4, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Reference Style Controls
        self.lbl_style = ctk.CTkLabel(self, text="Reference Style", font=sec_font)
        self.lbl_style.grid(row=5, column=0, padx=20, pady=(10, 5), sticky="w")
        self.ent_style = ctk.CTkEntry(self, placeholder_text="e.g. apa")
        self.ent_style.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Boolean Skip Switches
        self.switch_skip_journal = ctk.CTkSwitch(self, text="Skip Journal Update")
        self.switch_skip_journal.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.switch_skip_work = ctk.CTkSwitch(self, text="Skip Work Update")
        self.switch_skip_work.grid(row=8, column=0, padx=20, pady=10, sticky="w")


class MainFrame(ctk.CTkFrame):
    """Main content frame housing file picker buttons and the logging console."""

    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master, fg_color="transparent")
        self._create_widgets()

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
            self.io_frame, text="No manuscript file selected", anchor="w"
        )
        self.lbl_input_path.grid(row=0, column=1, padx=15, pady=15, sticky="ew")

        # Output Selection Controls
        self.btn_output = ctk.CTkButton(
            self.io_frame, text="Choose Output CSV", width=180
        )
        self.btn_output.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        self.lbl_output_path = ctk.CTkLabel(
            self.io_frame, text="No output CSV path selected", anchor="w"
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


class CiteCraftApp(ctk.CTk):
    """Root UI window class for the CiteCraft application using CTk 5.x."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_grid()

        # Mount Sidebar Left Frame
        self.sidebar = SidebarFrame(self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Mount Main Work Frame (Column 1)
        self.main_content = MainFrame(self)
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


if __name__ == "__main__":
    app = CiteCraftApp()
    app.mainloop()
