import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from llano_control.core import DEFAULT, load, save
from llano_control.gui import App

class SessionTests(unittest.TestCase):
    def app(self):
        data=copy.deepcopy(DEFAULT)
        p=copy.deepcopy(data['profiles']['Equilibrado'])
        p.update(rpm=1900,effect='Color Gradient',brightness=220,animation_speed=2,rgb_units='native',temperature_source='both')
        return SimpleNamespace(fields={},data=data,collect=Mock(return_value=('Gaming',p)),
                               gpu_id='GPU-nvidia',message=Mock())

    def test_unsaved_edits_round_trip_and_preserve_other_profiles(self):
        app=self.app()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'profiles.json'
            with patch('llano_control.gui.save',side_effect=lambda data:save(data,path)):
                self.assertTrue(App.persist_current(app))
            restored=load(path)
            self.assertEqual(restored['active'],'Gaming')
            self.assertEqual(restored['profiles']['Gaming'],app.collect.return_value[1])
            self.assertIn('Equilibrado',restored['profiles'])
            self.assertEqual(restored['display_gpu'],'GPU-nvidia')

    def test_unchanged_close_does_not_rewrite(self):
        app=self.app()
        with patch('llano_control.gui.save') as write:
            App.persist_current(app);App.persist_current(app)
        write.assert_called_once()

    def test_invalid_edit_keeps_last_saved_settings(self):
        app=self.app();before=copy.deepcopy(app.data)
        app.collect.side_effect=ValueError('Invalid curve')
        with patch('llano_control.gui.save') as write,patch('sys.stderr'):
            self.assertFalse(App.persist_current(app))
        write.assert_not_called();self.assertEqual(app.data,before)
        app.message.set_text.assert_called_once()

    def test_failed_write_keeps_previous_data(self):
        app=self.app();before=copy.deepcopy(app.data)
        with patch('llano_control.gui.save',side_effect=OSError('Disk full')),patch('sys.stderr'):
            self.assertFalse(App.persist_current(app))
        self.assertEqual(app.data,before)

    def test_hide_and_shutdown_flush_edits(self):
        app=self.app();app.tray_connected=True;app.win=Mock();app.tray=None
        with patch.object(App,'persist_current',return_value=True) as persist:
            App.hide_to_tray(app);App.cleanup_tray(app)
        self.assertEqual(persist.call_count,2)
        app.win.set_visible.assert_called_once_with(False)
        self.assertTrue(app.closed)

    def startup(self):
        return SimpleNamespace(closed=False,startup_apply_pending=True,startup_rgb_pending=False,
                               hardware_busy=Mock(return_value=False),apply_mode=Mock(),apply_rgb=Mock())

    def test_waits_for_existing_usb_operation(self):
        app=self.startup();app.hardware_busy.return_value=True
        App.apply_saved_on_startup(app)
        app.apply_mode.assert_not_called();app.apply_rgb.assert_not_called()
        self.assertTrue(app.startup_apply_pending)

    def test_rpm_then_rgb_once_after_completion(self):
        app=self.startup();order=[]
        def start_fan():
            order.append('rpm');app.hardware_busy.return_value=True
        app.apply_mode.side_effect=start_fan
        app.apply_rgb.side_effect=lambda:order.append('rgb')
        App.apply_saved_on_startup(app)
        App.apply_saved_on_startup(app)
        self.assertEqual(order,['rpm'])
        app.hardware_busy.return_value=False
        App.apply_saved_on_startup(app);App.apply_saved_on_startup(app)
        self.assertEqual(order,['rpm','rgb'])

    def test_rgb_still_runs_when_fan_cannot_start(self):
        app=self.startup() # apply_mode handles missing temperature by pausing its controller
        App.apply_saved_on_startup(app);App.apply_saved_on_startup(app)
        app.apply_mode.assert_called_once();app.apply_rgb.assert_called_once()

    def test_shutdown_prevents_startup_commands(self):
        app=self.startup();app.closed=True
        App.apply_saved_on_startup(app)
        app.apply_mode.assert_not_called();app.apply_rgb.assert_not_called()

    def test_hidden_startup_uses_first_sample_and_does_not_render(self):
        app=self.startup()
        app.win=Mock();app.win.get_visible.return_value=False
        app.sample_started=0;app.tick=Mock();app.drive_fan=Mock();app.send_tray=Mock()
        app.gpu_id='GPU-nvidia'
        sample={'cpu':{'temp':62},'gpus':[{'id':'GPU-nvidia','temp':51,'name':'NVIDIA'}]}
        seen=[];app.apply_mode.side_effect=lambda:seen.append(app.latest)
        with patch('llano_control.gui.GLib.timeout_add',return_value=1):
            App.receive(app,sample);App.receive(app,sample)
        self.assertEqual(seen,[sample])
        app.apply_rgb.assert_called_once()
        app.win.present.assert_not_called()
