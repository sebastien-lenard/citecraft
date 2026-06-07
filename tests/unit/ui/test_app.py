# tests/unit/ui/test_app.py
"""Unit tests for verification of the window layout scaffolding."""

import typing
from unittest.mock import MagicMock, patch

import pytest

from citecraft.ui.app import CiteCraftApp, MainFrame, SidebarFrame, UIState
from citecraft.utils.config import AppConfig


class StubStringVar:
    """A display-less replacement for ctk.StringVar for safe headless testing."""

    def __init__(
        self,
        master: object = None,
        value: str = "",
    ) -> None:
        self._value = str(value)

    def get(self) -> str:
        return self._value

    def set(self, val: str) -> None:
        self._value = str(val)


class StubBooleanVar:
    """A display-less replacement for ctk.BooleanVar for safe headless testing."""

    def __init__(
        self,
        master: object = None,
        value: bool = False,
    ) -> None:
        self._value = bool(value)

    def get(self) -> bool:
        return self._value

    def set(self, val: bool) -> None:
        self._value = bool(val)


def test_app_scaffolding_initialization() -> None:
    """Validate window configurations bypass display constraints on headless systems."""
    with (
        patch("customtkinter.CTk.__init__") as mock_init,
        patch("customtkinter.CTk.title") as mock_title,
        patch("customtkinter.CTk.geometry") as mock_geometry,
        patch("customtkinter.CTk.minsize") as mock_minsize,
        patch("customtkinter.CTk.grid_columnconfigure") as mock_col,
        patch("customtkinter.CTk.grid_rowconfigure") as mock_row,
        patch("citecraft.ui.app.UIState") as mock_state_cls,
        patch("citecraft.ui.app.SidebarFrame") as mock_sidebar,
        patch("citecraft.ui.app.MainFrame") as mock_main,
    ):
        mock_init.return_value = None
        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        app = CiteCraftApp()

        mock_init.assert_called_once()
        mock_title.assert_called_once_with(
            "CiteCraft — Manuscript Bibliography Generator"
        )
        mock_geometry.assert_called_once_with("1100x650")
        mock_minsize.assert_called_once_with(900, 500)
        mock_sidebar.assert_called_once_with(app, mock_state)
        mock_main.assert_called_once_with(app, mock_state)

        # First column is sidebar (fixed), second column is flexible
        mock_col.assert_any_call(0, weight=0)
        mock_col.assert_any_call(1, weight=1)


def test_sidebar_frame_creation() -> None:
    """Validate sidebar sub-components and elements configuration are initialized."""
    with (
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid_columnconfigure") as mock_col_config,
        patch("customtkinter.CTkLabel") as mock_label,
        patch("customtkinter.CTkComboBox") as mock_combo,
        patch("customtkinter.CTkEntry") as mock_entry,
        patch("customtkinter.CTkSwitch") as mock_switch,
        patch("customtkinter.CTkFont") as mock_font,
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_state = MagicMock()

        sidebar = SidebarFrame(mock_master, mock_state)

        mock_frame_init.assert_called_once_with(mock_master, width=280, corner_radius=0)

        # Verify grid layout constraints are called without hitting real tk engine
        mock_col_config.assert_called_once_with(0, weight=1)

        # Verify ComboBox for API selection binds the state's API variable
        mock_combo.assert_called_once_with(
            sidebar, values=["OpenAlex", "Crossref"], variable=mock_state.api
        )

        # Check expected text input counts (Journal and Style entries)
        assert mock_entry.call_count == 2

        # Check switches count (Skip updates configurations)
        assert mock_switch.call_count == 2


def test_main_frame_creation() -> None:
    """Validate main dashboard elements are initialized with expected layouts."""
    with (
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid") as mock_frame_grid,
        patch("customtkinter.CTkFrame.grid_columnconfigure") as mock_col_config,
        patch("customtkinter.CTkFrame.grid_rowconfigure") as mock_row_config,
        patch("customtkinter.CTkLabel") as mock_label,
        patch("customtkinter.CTkButton") as mock_button,
        patch("customtkinter.CTkTextbox") as mock_textbox,
        patch("customtkinter.CTkFont") as mock_font,
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_state = MagicMock()

        main_frame = MainFrame(mock_master, mock_state)

        # Frame should be transparent-backed
        mock_frame_init.assert_any_call(mock_master, fg_color="transparent")

        # Main frame layout alignments
        mock_col_config.assert_any_call(0, weight=1)
        mock_row_config.assert_any_call(2, weight=1)

        # Ensure grid alignment calls are bypassed on sub-frames
        mock_frame_grid.assert_called_once_with(
            row=0, column=0, padx=20, pady=(20, 10), sticky="ew"
        )

        # Checking existence of layout components (3 buttons: Input, Output, Run)
        assert mock_button.call_count == 3

        # Check console log panel instantiation
        mock_textbox.assert_called_once_with(main_frame)


def test_ui_state_initialization() -> None:
    """Validate default fallback properties are correctly loaded into state variables."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
    ):
        mock_master = MagicMock()
        state = UIState(mock_master)

        assert state.api.get() == "OpenAlex"
        assert state.style.get() == "apa"
        assert state.input_file_path.get() == "No manuscript file selected"
        assert state.output_file_path.get() == "No output CSV path selected"
        assert state.skip_journal_update.get() is False


def test_select_input_file_updates_state() -> None:
    """Validate input file dialog successfully updates the UIState."""
    with (
        patch("customtkinter.CTkFrame.__init__") as mock_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton"),
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
        patch("customtkinter.filedialog.askopenfilename") as mock_dialog,
    ):
        mock_init.return_value = None
        mock_dialog.return_value = "C:/mock/manuscript.docx"

        mock_state = MagicMock()
        main_frame = MainFrame(MagicMock(), mock_state)

        main_frame._select_input_file()

        mock_dialog.assert_called_once_with(
            title="Select Manuscript Document", filetypes=[("Word Documents", "*.docx")]
        )
        mock_state.input_file_path.set.assert_called_once_with(
            "C:/mock/manuscript.docx"
        )


def test_select_output_file_updates_state() -> None:
    """Validate output file selection successfully updates the UIState."""
    with (
        patch("customtkinter.CTkFrame.__init__") as mock_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton"),
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
        patch("customtkinter.filedialog.asksaveasfilename") as mock_dialog,
    ):
        mock_init.return_value = None
        mock_dialog.return_value = "C:/mock/output.csv"

        mock_state = MagicMock()
        main_frame = MainFrame(MagicMock(), mock_state)

        main_frame._select_output_file()

        mock_dialog.assert_called_once_with(
            title="Select Output CSV Location",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        mock_state.output_file_path.set.assert_called_once_with("C:/mock/output.csv")


def test_ui_state_serialization_success(test_config: AppConfig) -> None:
    """Validate UIState translates cleanly to strong typed PipelineOptions."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
    ):
        mock_master = MagicMock()
        state = UIState(mock_master)

        # Inject real values into Stub classes safely
        state.api.set("OpenAlex")
        state.journal_title.set("Geomorphology")
        state.style.set("apa")
        state.skip_journal_update.set(False)
        state.skip_work_update.set(True)
        state.input_file_path.set("C:/doc/manuscript.docx")
        state.output_file_path.set("C:/doc/output.csv")

        options = state.to_pipeline_options(test_config)

        assert options.api == "OpenAlex"
        assert options.input_file_path == "C:/doc/manuscript.docx"
        assert options.output_filepath == "C:/doc/output.csv"
        assert options.style == "apa"
        assert options.journal_title == "Geomorphology"
        assert options.skip_journal_update is False
        assert options.skip_work_update is True


def test_ui_state_serialization_validation_errors(test_config: AppConfig) -> None:
    """Validate validation checks raise descriptive ValueError exceptions."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
    ):
        mock_master = MagicMock()
        state = UIState(mock_master)

        state.api.set("OpenAlex")
        state.journal_title.set("")
        state.style.set("apa")
        state.skip_journal_update.set(False)
        state.skip_work_update.set(False)

        # Case 1: Unselected manuscript (Placeholder state value)
        state.input_file_path.set("No manuscript file selected")
        state.output_file_path.set("C:/output.csv")
        with pytest.raises(ValueError, match="Manuscript file must be selected"):
            state.to_pipeline_options(test_config)

        # Case 2: Unselected Output Path (Placeholder state value)
        state.input_file_path.set("C:/manuscript.docx")
        state.output_file_path.set("No output CSV path selected")
        with pytest.raises(ValueError, match="Output CSV destination path"):
            state.to_pipeline_options(test_config)

        # Case 3: Empty citation format style
        state.output_file_path.set("C:/output.csv")
        state.style.set("")
        with pytest.raises(ValueError, match="Reference Style cannot be empty"):
            state.to_pipeline_options(test_config)


def test_on_run_pipeline_validation_success(test_config: AppConfig) -> None:
    """Validate run event writes success to console log on valid state inputs."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton"),
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_state = UIState(mock_master)

        # Set valid variables
        mock_state.api.set("OpenAlex")
        mock_state.style.set("apa")
        mock_state.input_file_path.set("C:/doc/manuscript.docx")
        mock_state.output_file_path.set("C:/doc/output.csv")

        main_frame = MainFrame(mock_master, mock_state)
        main_frame.master = mock_master  # Bind mock master safely

        # Setup console stub mock to verify console output writes
        mock_textbox = MagicMock()
        main_frame.txt_console = mock_textbox

        with patch("citecraft.ui.app.get_config", return_value=test_config):
            main_frame._on_run_pipeline()

        # Verify normal state was set to write, and written value exists
        mock_textbox.configure.assert_any_call(state="normal")
        write_args = mock_textbox.insert.call_args[0][1]
        assert "Inputs Validated" in write_args
        assert "apa" in write_args


def test_on_run_pipeline_validation_failure(test_config: AppConfig) -> None:
    """Validate run event highlights widgets on validation value failures."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton"),
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_sidebar = MagicMock()
        mock_master.sidebar = mock_sidebar

        mock_state = UIState(mock_master)

        # Empty style to trigger validation error
        mock_state.api.set("OpenAlex")
        mock_state.style.set("")
        mock_state.input_file_path.set("C:/doc/manuscript.docx")
        mock_state.output_file_path.set("C:/doc/output.csv")

        main_frame = MainFrame(mock_master, mock_state)
        main_frame.master = mock_master  # Bind mock master safely

        mock_textbox = MagicMock()
        main_frame.txt_console = mock_textbox

        with patch("citecraft.ui.app.get_config", return_value=test_config):
            main_frame._on_run_pipeline()

        # Text box should log validation error message
        error_log = mock_textbox.insert.call_args[0][1]
        assert "Input Validation Error" in error_log
        assert "Reference Style cannot be empty" in error_log

        # Sidebar style entry should be configured to red border color
        mock_sidebar.ent_style.configure.assert_any_call(border_color="red")


def test_on_run_pipeline_manuscript_failure(test_config: AppConfig) -> None:
    """Validate manuscript path validation failure highlights btn_input."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton") as mock_button_cls,
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_state = UIState(mock_master)

        # Trigger manuscript validation error
        mock_state.api.set("OpenAlex")
        mock_state.style.set("apa")
        mock_state.input_file_path.set("No manuscript file selected")
        mock_state.output_file_path.set("C:/doc/output.csv")

        main_frame = MainFrame(mock_master, mock_state)
        main_frame.master = mock_master
        main_frame.txt_console = MagicMock()

        with patch("citecraft.ui.app.get_config", return_value=test_config):
            main_frame._on_run_pipeline()

        # Ensure btn_input configure border_color was highlighted
        typing.cast(MagicMock, main_frame.btn_input.configure).assert_called_with(
            border_color="red", border_width=2
        )


def test_on_run_pipeline_output_failure(test_config: AppConfig) -> None:
    """Validate output path validation failure highlights btn_output."""
    with (
        patch("customtkinter.StringVar", StubStringVar),
        patch("customtkinter.BooleanVar", StubBooleanVar),
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid"),
        patch("customtkinter.CTkFrame.grid_columnconfigure"),
        patch("customtkinter.CTkFrame.grid_rowconfigure"),
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton") as mock_button_cls,
        patch("customtkinter.CTkTextbox"),
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        mock_state = UIState(mock_master)

        # Trigger output destination validation error
        mock_state.api.set("OpenAlex")
        mock_state.style.set("apa")
        mock_state.input_file_path.set("C:/doc/manuscript.docx")
        mock_state.output_file_path.set("No output CSV path selected")

        main_frame = MainFrame(mock_master, mock_state)
        main_frame.master = mock_master
        main_frame.txt_console = MagicMock()

        with patch("citecraft.ui.app.get_config", return_value=test_config):
            main_frame._on_run_pipeline()

        # Ensure btn_output configure border_color was highlighted
        typing.cast(MagicMock, main_frame.btn_output.configure).assert_called_with(
            border_color="red", border_width=2
        )
