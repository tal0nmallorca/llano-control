import copy,csv,unittest
from pathlib import Path
from unittest.mock import patch
from llano_control.fan import FanController,fan_report,apply_fan,rpm_to_percent
from llano_control.core import DEFAULT


def state(first=0x80,percent=40,power=0):
    b=bytes([first,percent,power,3,4,2,127]);return b+bytes([(255-sum(b))&255])

class FanTests(unittest.TestCase):
    def profile(self,mode='Low'):
        p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']);p['mode']=mode;return p
    def test_observed_calibration_and_requested_steps(self):
        self.assertEqual([rpm_to_percent(x) for x in (1300,1550,1800)],[40,50,60])
        targets=[rpm_to_percent(x) for x in range(300,2801,100)]
        self.assertEqual(targets[0],1);self.assertEqual(targets[-1],100)
        self.assertEqual(targets,sorted(set(targets)))
    def test_matches_all_labeled_fan_and_power_commands(self):
        with (Path(__file__).parent/'fixtures/usb-events.csv').open() as f:rows=list(csv.DictReader(f))
        count=0
        for r in rows:
            if int(r['file'][:2])<51 or r['kind']!='set':continue
            command=bytes.fromhex(r['payload'])
            prior=[x for x in rows if x['file']==r['file'] and x['kind']=='response' and int(x['frame'])<int(r['frame'])][-1]
            self.assertEqual(fan_report(bytes.fromhex(prior['payload']),command[1],bool(command[0]),not bool(command[2])),command)
            count+=1
        self.assertEqual(count,59)
    def test_rgb_preserved_and_pc_control_only_explicit(self):
        for power in (0,1):
            for manual in (0x80,0x88):
                before=state(manual,power=power)
                report=fan_report(before,60)
                self.assertEqual(report[0],0);self.assertEqual(report[2:7],before[2:7])
                self.assertEqual(fan_report(before,60,True)[0],1)
    def test_physical_manual_and_off_stop_without_write(self):
        for before in (state(0x88),state(power=1)):
            class Device:
                def __enter__(self):return self
                def __exit__(self,*_):pass
                def state(self):return before
                def send(self,report):raise AssertionError('must not override hardware')
            self.assertTrue(apply_fan({'percent':60},Device)['paused'])
    def test_verify_write_and_noop(self):
        class Device:
            def __init__(self):self.value=state();self.sent=[]
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return self.value
            def send(self,report):
                self.sent.append(report);self.value=state(percent=report[1],power=report[2])
        d=Device()
        with patch('llano_control.fan.time.sleep'):
            self.assertFalse(apply_fan({'percent':40},lambda:d)['changed'])
            self.assertTrue(apply_fan({'percent':60,'take_control':True,'power':True},lambda:d)['changed'])
        self.assertEqual(len(d.sent),1)
    def test_missing_sensor_pauses_and_fixed_manual_needs_none(self):
        c=FanController(self.profile())
        with self.assertRaises(ValueError):c.plan(None,0)
        self.assertFalse(c.active)
        self.assertIsNotNone(FanController(self.profile('Manual')).plan(None,0))
    def test_curves_throttle_and_applied_snapshot(self):
        for mode,low,high in [('Low',300,1000),('Medium',600,2000),('High',1000,2800)]:
            profile=self.profile(mode);c=FanController(profile)
            profile['mode']='Manual'
            first=c.plan(30,0)
            self.assertEqual(first['percent'],rpm_to_percent(low));self.assertTrue(first['take_control'])
            c.completed({'power':True})
            self.assertIsNone(c.plan(90,4))
            last=c.plan(90,5);self.assertEqual(last['percent'],rpm_to_percent(high));self.assertFalse(last['take_control'])
            c.completed({'paused':True});self.assertIsNone(c.plan(90,10))
    def test_readback_mismatch_fails(self):
        class Device:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def state(self):return state()
            def send(self,_):pass
        with patch('llano_control.fan.time.sleep'),self.assertRaises(OSError):apply_fan({'percent':60},Device)
