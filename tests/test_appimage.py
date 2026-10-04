import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from llano_control.gui import App

class AppImageTests(unittest.TestCase):
    def test_autostart_uses_persistent_appimage_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'autostart.desktop'
            app=SimpleNamespace(auto_path=lambda:target,auto=Mock(),message=Mock())
            app.auto.get_active.return_value=True
            with patch.dict(os.environ,{'APPIMAGE':'/home/user/Apps/Llano Control.AppImage'}):
                App.autostart(app)
            self.assertIn('Exec="/home/user/Apps/Llano Control.AppImage" gui',target.read_text())
            self.assertNotIn('/tmp/.mount_',target.read_text())

    def test_source_autostart_keeps_normal_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'autostart.desktop'
            app=SimpleNamespace(auto_path=lambda:target,auto=Mock(),message=Mock())
            app.auto.get_active.return_value=True
            with patch.dict(os.environ,{'APPIMAGE':''}):App.autostart(app)
            self.assertIn('/llano-control" gui',target.read_text())
