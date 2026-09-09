import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from llano_control.gui import App

class TrayTests(unittest.TestCase):
    def fake(self,connected):
        return SimpleNamespace(tray_connected=connected,win=Mock(),message=Mock(),closed=False)
    def test_hide_only_with_connected_tray(self):
        app=self.fake(True); App.hide_to_tray(app)
        app.win.set_visible.assert_called_once_with(False)
        app=self.fake(False); App.hide_to_tray(app)
        app.win.set_visible.assert_not_called(); app.message.set_text.assert_called_once()
    def test_close_keeps_monitor_running(self):
        app=self.fake(True); app.hide_to_tray=Mock()
        self.assertTrue(App.on_close(app)); self.assertFalse(app.closed)
        app.hide_to_tray.assert_called_once()
    def test_lost_tray_restores_window(self):
        app=self.fake(True); app.win.get_visible.return_value=False
        App.tray_event(app,{'event':'connection','connected':False})
        app.win.present.assert_called_once(); self.assertFalse(app.tray_connected)
    def test_explicit_exit(self):
        app=self.fake(True); app.quit=Mock()
        App.tray_event(app,{'event':'quit'}); app.quit.assert_called_once()
    def test_closed_app_ignores_late_events(self):
        app=self.fake(True); app.closed=True
        App.tray_event(app,{'event':'show'}); app.win.present.assert_not_called()

    def test_startup_waits_without_showing_window(self):
        app=self.fake(False); app.startup_pending=True
        App.tray_event(app,{'event':'connection','connected':False})
        app.win.present.assert_not_called()
    def test_startup_connected_stays_hidden(self):
        app=self.fake(False); app.startup_pending=True
        App.tray_event(app,{'event':'connection','connected':True})
        App.finish_startup(app)
        app.win.present.assert_not_called()
        self.assertFalse(app.startup_pending)
    def test_startup_timeout_without_tray_shows_window(self):
        app=self.fake(False); app.startup_pending=True
        App.finish_startup(app)
        app.win.present.assert_called_once()
