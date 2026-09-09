import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from llano_control.core import DEFAULT, validate, save, load, Preview, interpolate
from llano_control.backend import HardwareBackend, UnsupportedProtocol
from llano_control.devices import inventory, difference
from llano_control.__main__ import capture

class Tests(unittest.TestCase):
    def test_persistence_and_rejected_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json'; save(DEFAULT,p)
            invalid=copy.deepcopy(DEFAULT); invalid['profiles']['Equilibrado']['rpm']=9999
            with self.assertRaises(ValueError): save(invalid,p)
            self.assertEqual(load(p),DEFAULT)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
    def test_curve(self):
        self.assertEqual(interpolate([[30,600],[50,1000]],40),800)
        self.assertEqual(interpolate([[30,600],[50,1000]],0),600)
        self.assertEqual(interpolate([[30,600],[50,1000]],100),1000)
    def test_hysteresis_and_sensor_loss(self):
        p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']); p['mode']='Custom'; v=Preview()
        first=v.calculate(p,50); self.assertEqual(v.calculate(p,52),first)
        self.assertNotEqual(v.calculate(p,54),first)
        self.assertIsNone(v.calculate(p,None)); self.assertIsNone(v.last_rpm)
    def test_invalid_curves(self):
        for curve in ([[40,600],[40,1000]], [[float('nan'),600],[70,1000]], [[30,0],[70,1000]]):
            d=copy.deepcopy(DEFAULT); d['profiles']['Equilibrado']['curve']=curve
            with self.assertRaises(ValueError): validate(d)
    def test_backend_never_writes(self):
        with patch('os.open',side_effect=AssertionError('opened hardware')):
            with self.assertRaises(UnsupportedProtocol): HardwareBackend().apply(DEFAULT)
    def test_capture_rejects_unrelated(self):
        with patch('llano_control.__main__.inventory',return_value={'hid':[]}), patch('os.open',side_effect=AssertionError('opened hardware')):
            with self.assertRaises(ValueError): capture('/dev/hidraw0',1)
    def test_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); usb=root/'bus/usb/devices/1-2'; usb.mkdir(parents=True)
            (usb/'idVendor').write_text('374a'); (usb/'idProduct').write_text('b101')
            result=inventory(root); self.assertTrue(result['usb'][0]['candidate'])
            self.assertEqual(len(difference({'usb':[],'hid':[]},result)['usb']['added']),1)
    def test_broken_config_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'broken'; p.write_text('{')
            with self.assertRaises(json.JSONDecodeError): load(p)
            self.assertEqual(p.read_text(),'{')

if __name__=='__main__': unittest.main()

class RPMStepTests(unittest.TestCase):
    def test_steps_and_legacy_values(self):
        from llano_control.core import rpm_step
        for value in range(300,2801,100): self.assertEqual(rpm_step(value),value)
        self.assertEqual(rpm_step(1250),1300)
        self.assertEqual(rpm_step(1249),1200)
        for value in (299,2801):
            with self.assertRaises(ValueError): rpm_step(value)

class AIModeTests(unittest.TestCase):
    def test_requested_ranges_and_steps(self):
        from llano_control.core import effective_curve
        for mode,limits in [('Low',(300,1000)),('Medium',(600,2000)),('High',(1000,2800))]:
            p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']); p['mode']=mode
            preview=Preview()
            self.assertEqual(preview.calculate(p,0),limits[0])
            self.assertEqual(preview.calculate(p,110),limits[1])
            self.assertEqual((effective_curve(p)[0][1],effective_curve(p)[-1][1]),limits)
            for temp in range(111):
                rpm=preview.calculate(p,temp)
                self.assertTrue(limits[0]<=rpm<=limits[1]); self.assertEqual(rpm%100,0)
    def test_switch_mode_does_not_reuse_out_of_range_hysteresis(self):
        p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']); p['mode']='High'
        v=Preview(); self.assertEqual(v.calculate(p,90),2800)
        p['mode']='Low'; self.assertEqual(v.calculate(p,90),1000)
        p['power']=False; self.assertIsNone(v.calculate(p,90))
    def test_custom_curve_and_manual_display_preserved(self):
        from llano_control.core import effective_curve
        p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']); p['mode']='Custom'
        self.assertEqual(effective_curve(p),p['curve'])
        p['mode']='Manual'; self.assertEqual(effective_curve(p),((0,1200),(110,1200)))
