import json
import os
import tempfile
from unittest.mock import patch

from server.routes.optimizer import _get_settings, _save_settings


def test_get_settings_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "optimizer_settings.json")
        with patch("server.routes.optimizer._SETTINGS_PATH", path):
            settings = _get_settings()
            assert settings["max_cost"] == 70.5
            assert settings["num_forwards"] == 6


def test_save_and_get_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "optimizer_settings.json")
        with patch("server.routes.optimizer._SETTINGS_PATH", path):
            _save_settings({"max_cost": 80.0, "num_forwards": 7})
            settings = _get_settings()
            assert settings["max_cost"] == 80.0
            assert settings["num_forwards"] == 7
            # Other fields should still be defaults
            assert settings["num_defensemen"] == 4
