# tests/unit/ui/test_app.py
"""Unit tests for verification of the window layout scaffolding."""

from unittest.mock import MagicMock, patch

from citecraft.ui.app import CiteCraftApp, MainFrame, SidebarFrame


def test_app_scaffolding_initialization() -> None:
    """Validate window configurations bypass display constraints on headless systems."""
    with (
        patch("customtkinter.CTk.__init__") as mock_init,
        patch("customtkinter.CTk.title") as mock_title,
        patch("customtkinter.CTk.geometry") as mock_geometry,
        patch("customtkinter.CTk.minsize") as mock_minsize,
        patch("customtkinter.CTk.grid_columnconfigure") as mock_col,
        patch("customtkinter.CTk.grid_rowconfigure"),
        patch("citecraft.ui.app.SidebarFrame") as mock_sidebar,
        patch("citecraft.ui.app.MainFrame") as mock_main,
    ):
        mock_init.return_value = None
        app = CiteCraftApp()

        mock_init.assert_called_once()
        mock_title.assert_called_once_with(
            "CiteCraft — Manuscript Bibliography Generator"
        )
        mock_geometry.assert_called_once_with("1100x650")
        mock_minsize.assert_called_once_with(900, 500)
        mock_sidebar.assert_called_once_with(app)
        mock_main.assert_called_once_with(app)

        # First column is sidebar (fixed), second column is flexible
        mock_col.assert_any_call(0, weight=0)
        mock_col.assert_any_call(1, weight=1)


def test_sidebar_frame_creation() -> None:
    """Validate sidebar sub-components and elements configuration are initialized."""
    with (
        patch("customtkinter.CTkFrame.__init__") as mock_frame_init,
        patch("customtkinter.CTkFrame.grid_columnconfigure") as mock_col_config,
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkComboBox") as mock_combo,
        patch("customtkinter.CTkEntry") as mock_entry,
        patch("customtkinter.CTkSwitch") as mock_switch,
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        sidebar = SidebarFrame(mock_master)

        mock_frame_init.assert_called_once_with(mock_master, width=280, corner_radius=0)

        # Verify grid layout constraints are called without hitting real tk engine
        mock_col_config.assert_called_once_with(0, weight=1)

        # Verify ComboBox for API selection
        mock_combo.assert_called_once_with(sidebar, values=["OpenAlex", "Crossref"])

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
        patch("customtkinter.CTkLabel"),
        patch("customtkinter.CTkButton") as mock_button,
        patch("customtkinter.CTkTextbox") as mock_textbox,
        patch("customtkinter.CTkFont"),
    ):
        mock_frame_init.return_value = None
        mock_master = MagicMock()
        main_frame = MainFrame(mock_master)

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
