import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('capture_mythcool',Path(__file__).resolve().parents[1]/'tools/capture-mythcool.py')
capture=importlib.util.module_from_spec(spec); spec.loader.exec_module(capture)

class CaptureSelectionTests(unittest.TestCase):
    def device(self,**changes):
        return dict(path='3-5',bus='3',address='9',candidate=True,**changes)
    def test_only_unambiguous_candidate(self):
        self.assertEqual(capture.select_device([self.device()])[1:],(3,9))
        for devices in ([],[self.device(),self.device()]):
            with self.assertRaises(ValueError): capture.select_device(devices)
    def test_explicit_verified_port(self):
        dev=self.device(); dev['candidate']=False
        with self.assertRaises(ValueError): capture.select_device([dev])
        self.assertEqual(capture.select_device([dev],'3-5')[1:],(3,9))
    def test_reject_invalid_address(self):
        for value in ('128','0','9;echo bad'):
            dev=self.device(); dev['address']=value
            with self.assertRaises(ValueError): capture.select_device([dev])
