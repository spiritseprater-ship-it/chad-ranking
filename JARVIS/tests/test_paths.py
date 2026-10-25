"""Tests for paths.py - location behaviour in source and packaged mode.

The packaged build is the risky case: PyInstaller puts the sources under
``<bundle>/_internal``, so a naive ``Path(__file__).parent`` points inside the
bundle instead of at the folder the user extracted.  These tests pin the
behaviour that makes the EXE work from any folder.
"""

import json
import sys
from pathlib import Path

import pytest

import paths


@pytest.fixture
def userdata(tmp_path, monkeypatch):
    """Redirect the per-user data folder to a temp dir."""
    target = tmp_path / "userdata"
    monkeypatch.setenv("JARVIS_USER_DATA_DIR", str(target))
    return target


def _freeze(monkeypatch, exe: Path, meipass: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)


class TestSourceMode:
    def test_application_dir_is_the_jarvis_folder(self, monkeypatch):
        monkeypatch.delenv("JARVIS_USER_DATA_DIR", raising=False)
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert paths.application_dir() == Path(paths.__file__).resolve().parent

    def test_resource_dir_is_the_jarvis_folder(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert paths.resource_dir() == Path(paths.__file__).resolve().parent

    def test_entry_path_points_at_main_py(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert paths.entry_path().endswith("main.py")

    def test_log_dir_lives_in_user_data(self, userdata):
        assert paths.log_dir() == userdata / "logs"


class TestFrozenMode:
    def test_application_dir_is_the_folder_holding_the_exe(self, monkeypatch, tmp_path):
        bundle = tmp_path / "JARVIS"
        bundle.mkdir()
        exe = bundle / "JARVIS.exe"
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, bundle / "_internal")
        assert paths.application_dir() == bundle

    def test_resource_dir_is_meipass_not_application_dir(self, monkeypatch, tmp_path):
        bundle = tmp_path / "JARVIS"
        internal = bundle / "_internal"
        internal.mkdir(parents=True)
        exe = bundle / "JARVIS.exe"
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, internal)
        assert paths.resource_dir() == internal
        assert paths.resource_dir() != paths.application_dir()

    def test_entry_path_is_the_exe(self, monkeypatch, tmp_path):
        exe = tmp_path / "JARVIS" / "JARVIS.exe"
        exe.parent.mkdir()
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, exe.parent / "_internal")
        assert paths.entry_path() == str(exe)

    def test_asset_paths_come_from_the_bundle(self, monkeypatch, tmp_path):
        bundle = tmp_path / "JARVIS"
        internal = bundle / "_internal"
        (internal / "assets").mkdir(parents=True)
        exe = bundle / "JARVIS.exe"
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, internal)
        assert paths.resource_path("assets") == internal / "assets"


class TestUserDataDir:
    def test_override_env_var_wins(self, userdata):
        assert paths.user_data_dir() == userdata

    def test_windows_uses_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.delenv("JARVIS_USER_DATA_DIR", raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        monkeypatch.setattr(sys, "platform", "win32")
        assert paths.user_data_dir() == tmp_path / "appdata" / "JARVIS"

    def test_non_windows_falls_back_to_home(self, monkeypatch):
        monkeypatch.delenv("JARVIS_USER_DATA_DIR", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        assert paths.user_data_dir() == Path.home() / ".jarvis"


class TestConfigBootstrap:
    def _bundle(self, tmp_path, monkeypatch):
        bundle = tmp_path / "JARVIS"
        internal = bundle / "_internal"
        internal.mkdir(parents=True)
        (internal / "config.json").write_text(
            json.dumps({"gemini": {"api_key": "", "enabled": True}}), encoding="utf-8"
        )
        exe = bundle / "JARVIS.exe"
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, internal)
        return bundle, internal

    def test_first_run_copies_default_config_into_user_data(
        self, monkeypatch, tmp_path, userdata
    ):
        bundle, internal = self._bundle(tmp_path, monkeypatch)
        assert not (userdata / "config.json").exists()

        target = paths.ensure_user_config()

        assert target == userdata / "config.json"
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8"))["gemini"]["enabled"] is True
        # the bundled default is left untouched
        assert (internal / "config.json").exists()

    def test_existing_user_config_is_not_clobbered(self, monkeypatch, tmp_path, userdata):
        bundle, internal = self._bundle(tmp_path, monkeypatch)
        userdata.mkdir(parents=True, exist_ok=True)
        existing = userdata / "config.json"
        existing.write_text(json.dumps({"marker": "user"}), encoding="utf-8")

        paths.ensure_user_config()

        assert json.loads(existing.read_text(encoding="utf-8")) == {"marker": "user"}

    def test_default_config_path_falls_back_to_canonical_user_data(
        self, monkeypatch, tmp_path
    ):
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setattr(paths, "user_data_dir", lambda: empty)
        monkeypatch.setattr(paths, "application_dir", lambda: empty)
        monkeypatch.setattr(paths, "resource_dir", lambda: empty)
        # no config anywhere yet: still resolves to the writable user data dir
        assert paths.default_config_path() == empty / "config.json"

    def test_existing_user_config_wins_over_bundled_default(
        self, monkeypatch, tmp_path, userdata
    ):
        self._bundle(tmp_path, monkeypatch)
        userdata.mkdir(parents=True, exist_ok=True)
        (userdata / "config.json").write_text("{}", encoding="utf-8")
        assert paths.default_config_path() == userdata / "config.json"

    def test_config_next_to_the_application_is_used(self, monkeypatch, tmp_path, userdata):
        bundle, internal = self._bundle(tmp_path, monkeypatch)
        (bundle / "config.json").write_text("{}", encoding="utf-8")
        assert paths.default_config_path() == bundle / "config.json"

    def test_bundled_only_config_is_still_found(self, monkeypatch, tmp_path, userdata):
        self._bundle(tmp_path, monkeypatch)
        # before first run the read-only bundled default is the only config there
        assert paths.default_config_path() == (tmp_path / "JARVIS" / "_internal" / "config.json")


class TestDotenv:
    def test_finds_dotenv_in_user_data(self, monkeypatch, tmp_path, userdata):
        userdata.mkdir(parents=True, exist_ok=True)
        env_file = userdata / ".env"
        env_file.write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
        assert paths.find_dotenv() == env_file

    def test_finds_dotenv_next_to_the_application(self, monkeypatch, tmp_path, userdata):
        bundle = tmp_path / "JARVIS"
        bundle.mkdir(parents=True)
        (bundle / ".env").write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
        exe = bundle / "JARVIS.exe"
        exe.write_bytes(b"MZ")
        _freeze(monkeypatch, exe, bundle / "_internal")
        assert paths.find_dotenv() == bundle / ".env"

    def test_returns_none_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path / "a")
        monkeypatch.setattr(paths, "application_dir", lambda: tmp_path / "b")
        monkeypatch.setattr(paths, "resource_dir", lambda: tmp_path / "c")
        assert paths.find_dotenv() is None
