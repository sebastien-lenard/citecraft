# tests/unit/utils/test_paths.py
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from citecraft.utils import paths


@pytest.fixture(autouse=True)
def clear_env_cache():
    """Reset the internal module _ENV before each test for isolation."""
    with patch.dict(os.environ, {}, clear=True):
        paths._ENV = {"APP_NAME": "citecraft"}
        yield


class TestAppNaming:
    def test_default_app_name(self) -> None:
        """Should fall back to standard app name if nothing is configured."""
        assert paths.get_app_name() == "citecraft"

    def test_custom_app_name_from_env(self) -> None:
        """Should respect APP_NAME from environment variables and strip quotes."""
        paths._ENV["APP_NAME"] = '"custom-app-name"'
        assert paths.get_app_name() == "custom-app-name"


class TestOSBaseDirectories:
    @pytest.mark.parametrize(
        "target_os, mock_home, extra_env, expected_subpath",
        [
            # 1. Windows Configuration
            (
                "Windows",
                "C:/Users/TestUser",
                {"LOCALAPPDATA": "C:/Users/TestUser/AppData/Local"},
                "C:/Users/TestUser/AppData/Local/citecraft",
            ),
            # 2. macOS Configuration
            (
                "Darwin",
                "/Users/TestUser",
                {},
                "/Users/TestUser/Library/citecraft",
            ),
            # 3. Linux Configuration
            (
                "Linux",
                "/home/testuser",
                {},
                "/home/testuser/.local/state/citecraft",
            ),
        ],
        ids=["windows_default", "macos_default", "linux_default"],
    )
    def test_default_os_paths(
        self, target_os, mock_home, extra_env, expected_subpath,
    ) -> None:
        """Should map to the correct OS-specific data directory structure."""
        # Dynamically apply any specific environment variables required for the platform
        paths._ENV.update(extra_env)

        with (
            patch("platform.system", return_value=target_os),
            patch("pathlib.Path.home", return_value=Path(mock_home)),
        ):
            assert paths.get_app_base_dir() == Path(expected_subpath)

    def test_global_app_base_dir_override(self) -> None:
        """Setting APP_BASE_DIR should bypass OS-level checks completely."""
        paths._ENV["APP_BASE_DIR"] = "/var/log/my_app"
        assert paths.get_app_base_dir() == Path("/var/log/my_app").resolve()


class TestSafeDirectoryResolutionRealErrors:
    def test_successful_directory_creation(self, tmp_path: Path) -> None:
        """REAL TEST: Verifies successful path creation on the actual filesystem."""
        # Point the app base directory to a valid, writable real temp location
        paths._ENV["APP_BASE_DIR"] = str(tmp_path)

        resolved_path, intended_path, is_fallback = paths.get_safe_dir("logs")

        expected_target = tmp_path / "logs"
        assert resolved_path == expected_target
        assert intended_path == expected_target
        assert resolved_path.exists()
        assert resolved_path.is_dir()
        assert is_fallback is False

    def test_fallback_triggered_by_invalid_parent_type(self, tmp_path: Path) -> None:
        """Force an OS error by using a file as a parent directory path.
        Test cannot work using os.chmod because it only affects files on Windows."""
        # 1. Create a regular file where the base dir is expected to be
        bad_parent = tmp_path / "blocked_file_root"
        bad_parent.touch()

        # 2. Tell our module to treat this file as the base directory
        paths._ENV["APP_BASE_DIR"] = str(bad_parent)

        # 3. Create a sandbox for the temp fallback
        fallback_sandbox = tmp_path / "system_temp"
        fallback_sandbox.mkdir()

        with patch("tempfile.gettempdir", return_value=str(fallback_sandbox)):
            # This will call: Path("blocked_file_root/logs").mkdir(parents=True)
            # Because 'blocked_file_root' is a file, the OS throws an error.
            resolved_path, _, is_fallback = paths.get_safe_dir("logs")

            # Assertions
            assert is_fallback is True
            assert fallback_sandbox in resolved_path.parents
            assert resolved_path.exists()

    def test_fallback_triggered_by_file_collision(self, tmp_path: Path) -> None:
        """REAL TEST: Forces an OSError/FileExistsError.

        If a regular file already exists exactly where the application wants
        to build its directory tree, mkdir will fail hard on any OS.
        """
        # Create a physical file named 'citecraft'
        collision_file = tmp_path / "citecraft"
        collision_file.touch()

        # Point the base directory to this exact file path
        paths._ENV["APP_BASE_DIR"] = str(collision_file)

        fallback_sandbox = tmp_path / "system_temp"
        fallback_sandbox.mkdir()

        with patch("tempfile.gettempdir", return_value=str(fallback_sandbox)):
            # This will physically fail because you can't create a subfolder
            # inside a plain text file.
            resolved_path, intended_path, is_fallback = paths.get_safe_dir("logs")

            assert is_fallback is True
            assert resolved_path.exists()
            assert "system_temp" in resolved_path.parts
            assert intended_path == collision_file / "logs"
