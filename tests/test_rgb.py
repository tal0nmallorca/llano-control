import csv
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from llano_control.rgb import rgb_report, checked_state, apply_rgb, HidFeature, COLORS
from llano_control.core import EFFECTS, DEFAULT, validate

class RGBTests(unittest.TestCase):
    def test_all_labeled_rgb_commands_match_capture(self):
        with (Path(__file__).parent/'fixtures/usb-events.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        count=0
        for row in rows:
            if not 10<=int(row['file'][:2])<=44 or row['kind']!='set': continue
            report=bytes.fromhex(row['payload'])
            previous=[r for r in rows if r['file']==row['file'] and r['kind']=='response' and int(r['frame'])<int(row['frame'])][-1]
            state=bytes.fromhex(previous['payload'])
            settings=dict(rgb=not bool(report[3]&128),effect=EFFECTS[report[3]&127],
                          color=next(c for c,v in COLORS.items() if v==report[4]),
                          animation_speed=3-report[5],brightness=report[6])
            self.assertEqual(rgb_report(state,settings),report);count+=1
        self.assertEqual(count,16)
    def settings(self): return dict(rgb=True,effect=EFFECTS[0],color='#3985ff',brightness=127,animation_speed=2)
    def test_manual_and_power_preserved_without_takeover(self):
        body=bytes.fromhex('88 28 01 03 04 00 ff');state=body+bytes([(255-sum(body))&255])
        report=rgb_report(state,self.settings())
        self.assertEqual(report[:3],bytes([0,40,1]));self.assertEqual(sum(report)&255,255)
        self.assertEqual(report[3:7],bytes([0,1,1,127]))
    def test_bad_state_and_inputs_rejected(self):
        with self.assertRaises(ValueError):checked_state(bytes(8))
        state=bytes.fromhex('80 01 00 03 04 00 ff 78')
        for key,value in [('color','#123456'),('animation_speed',4),('brightness',256),('brightness',True)]:
            settings=self.settings();settings[key]=value
            with self.assertRaises(ValueError):rgb_report(state,settings)
    def test_unnumbered_get_and_zero_prefix_send(self):
        device=HidFeature();device.fd=123
        payload=bytes.fromhex('88 01 00 00 00 00 ff 77')
        def ioctl(fd,code,buf):
            if (code&255)==6:
                self.assertEqual(bytes(buf),bytes.fromhex('00 80 00 00 00 00 00 00 7f'));return 9
            buf[:8]=payload;return 8
        with patch('llano_control.rgb.fcntl.ioctl',side_effect=ioctl),patch('llano_control.rgb.time.sleep'):
            self.assertEqual(device.state(),payload)
    def test_readback_failure_is_not_success(self):
        state=bytes.fromhex('80 01 00 03 04 00 ff 78')
        class Fake:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return state
            def send(self,report):self.report=report
        with patch('llano_control.rgb.time.sleep'),self.assertRaises(OSError):apply_rgb(self.settings(),Fake)
    def test_profiles_old_and_native(self):
        data=copy.deepcopy(DEFAULT);validate(data)
        p=data['profiles'][data['active']];p.update(rgb_units='native',brightness=127,animation_speed=3);validate(data)
        p['animation_speed']=4
        with self.assertRaises(ValueError):validate(data)
