import copy,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from llano_control.gui import App
from llano_control.core import DEFAULT
from llano_control.fan import FanController

class FanUITests(unittest.TestCase):
    def test_automatic_cycle_does_not_flash_controls_or_progress(self):
        controller=FanController(copy.deepcopy(DEFAULT['profiles']['Equilibrado']))
        controller.initial=False
        app=SimpleNamespace(fan_controller=controller,hardware_busy=lambda:False,
                            executor=Mock(),fan_status=Mock(),update_hardware_buttons=Mock())
        App.drive_fan(app,{'cpu':{'temp':60}})
        self.assertTrue(app.fan_busy);self.assertFalse(app.fan_explicit)
        app.fan_status.set_text.assert_not_called();app.update_hardware_buttons.assert_not_called()
        app.executor.submit.assert_called_once()
    def test_background_busy_keeps_buttons_enabled(self):
        buttons=[Mock() for _ in range(4)]
        for button in buttons:button.get_sensitive.return_value=True
        app=SimpleNamespace(rgb_busy=False,power_busy=False,fan_explicit=False,fan_busy=True,
                            apply_button=buttons[0],fan_stop=buttons[1],rgb_apply=buttons[2],power_toggle=buttons[3])
        App.update_hardware_buttons(app)
        for button in buttons:button.set_sensitive.assert_not_called()
    def test_click_during_background_cycle_is_queued_and_delivered(self):
        controller=SimpleNamespace(active=False)
        app=SimpleNamespace(fan_busy=True,fan_explicit=False,update_hardware_buttons=Mock(),
                            closed=False,fan_controller=controller)
        callback=Mock()
        self.assertTrue(App.defer_during_fan(app,callback,True))
        with patch('llano_control.gui.GLib.idle_add') as idle:
            App.fan_finished(app,controller,None,None)
        idle.assert_called_once_with(callback,True)
        self.assertIsNone(app.pending_hardware_action)
