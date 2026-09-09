import tempfile,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from llano_control.power_position import load_position,save_position,path
from llano_control.gui import App

class PositionTests(unittest.TestCase):
    def test_persistence_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',XDG_CONFIG_HOME=d):
            self.assertIsNone(load_position())
            for value in (True,False):save_position(value);self.assertIs(load_position(),value)
            for data in ('bad','[]','{"power":1}'):
                path().write_text(data);self.assertIsNone(load_position())
    def test_confirmation_updates_switch_without_usb_feedback(self):
        app=SimpleNamespace(power_confirmed=False,power_switch_updating=False,power_toggle=Mock(),power_status=Mock(),set_device_power=Mock(),hardware_busy=lambda:False)
        app.power_toggle.set_active.side_effect=lambda value:App.power_switch_changed(app,app.power_toggle,value)
        with patch('llano_control.gui.save_position') as save:
            App.update_power_indicator(app,True)
            App.update_power_indicator(app,True)
            save.assert_called_once_with(True)
        app.set_device_power.assert_not_called()
        app.power_toggle.set_state.assert_called_with(True)
        self.assertFalse(app.power_switch_updating)
    def test_failure_restores_last_confirmed_position(self):
        app=SimpleNamespace(power_confirmed=True,power_switch_updating=False,power_toggle=Mock(),power_status=Mock())
        with patch('llano_control.gui.save_position') as save:App.update_power_indicator(app,None)
        save.assert_not_called();app.power_toggle.set_active.assert_called_with(True)
    def test_user_requests_explicit_position(self):
        app=SimpleNamespace(power_switch_updating=False,hardware_busy=lambda:False,set_device_power=Mock())
        widget=Mock();self.assertTrue(App.power_switch_changed(app,widget,False))
        app.set_device_power.assert_called_once_with(widget,False)
