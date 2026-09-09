import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from llano_control.fan import power_report,apply_power
from llano_control.gui import App

class PowerTests(unittest.TestCase):
    def test_exact_captured_on_off_pair(self):
        on=bytes.fromhex('80 33 00 00 00 00 ff 4d')
        off=bytes.fromhex('80 33 01 00 00 00 ff 4c')
        self.assertEqual(power_report(on,False),bytes.fromhex('00 33 01 00 00 00 ff cc'))
        self.assertEqual(power_report(off,True),bytes.fromhex('00 33 00 00 00 00 ff cd'))
    def test_preserves_rgb_and_percentage_in_manual(self):
        body=bytes.fromhex('88 28 00 83 04 02 7f');state=body+bytes([(255-sum(body))&255])
        report=power_report(state,False)
        self.assertEqual(report[0],0);self.assertEqual(report[1],40)
        self.assertEqual(report[3:7],state[3:7]);self.assertEqual(sum(report)&255,255)
    def test_readback_and_noop(self):
        class Device:
            def __init__(self):self.value=bytes.fromhex('80 33 00 00 00 00 ff 4d');self.sent=[]
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return self.value
            def send(self,report):
                self.sent.append(report);body=bytes([0x80])+report[1:7]
                self.value=body+bytes([(255-sum(body))&255])
        device=Device()
        with patch('llano_control.fan.time.sleep'):
            self.assertFalse(apply_power(True,lambda:device)['changed'])
            self.assertFalse(apply_power(False,lambda:device)['power'])
            self.assertTrue(apply_power(True,lambda:device)['power'])
        self.assertEqual(len(device.sent),2)
    def test_toggle_reads_current_state_each_time(self):
        class Device:
            def __init__(self):self.value=bytes.fromhex('80 33 00 00 00 00 ff 4d')
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return self.value
            def send(self,report):
                body=bytes([0x80])+report[1:7];self.value=body+bytes([(255-sum(body))&255])
        device=Device()
        with patch('llano_control.fan.time.sleep'):
            self.assertFalse(apply_power(None,lambda:device,toggle=True)['power'])
            self.assertTrue(apply_power(None,lambda:device,toggle=True)['power'])

    def test_failed_readback_not_success(self):
        class Device:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return bytes.fromhex('80 33 00 00 00 00 ff 4d')
            def send(self,report):pass
        with patch('llano_control.fan.time.sleep'),self.assertRaises(OSError):apply_power(False,Device)
        with self.assertRaises(ValueError):apply_power(1,Device)
    def test_gui_pauses_curve_and_sends_only_power(self):
        app=SimpleNamespace(set_device_power=Mock(),defer_during_fan=lambda *args:False,hardware_busy=lambda:False,fan_controller=SimpleNamespace(active=True),
                            fan_status=Mock(),power_status=Mock(),update_hardware_buttons=Mock(),
                            executor=Mock(),power_finished=Mock())
        app.executor.submit.side_effect=lambda work:work()
        with patch('llano_control.gui.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"power": false}')) as run,patch('llano_control.gui.GLib.idle_add') as idle:
            App.set_device_power(app,None,False)
        self.assertFalse(app.fan_controller.active)
        self.assertIn('"operation": "power"',run.call_args.args[0][-1])
        self.assertNotIn('percent',run.call_args.args[0][-1])
        idle.assert_called_once()
