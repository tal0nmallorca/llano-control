import copy
import json
import unittest
from pathlib import Path
from llano_control.drm_clients import parse,ClientMonitor

class DRMTests(unittest.TestCase):
    def fixture(self):
        return json.loads((Path(__file__).parent/'fixtures/intel-vpp.json').read_text())
    def test_actual_capture(self):
        monitor=ClientMonitor()
        for sample in self.fixture():
            clients={}
            for fields in sample['clients'].values():
                ident,entry=parse('\n'.join(k+': '+v for k,v in fields.items()),'0000:00:02.0')
                clients[ident]=entry
            result=monitor.calculate('0000:00:02.0',clients,sample['monotonic'])
        self.assertAlmostEqual(result['engines']['video-enhance'],33.313,places=2)
        self.assertEqual(result['resident_bytes'],32352*1024)
        self.assertEqual(result['allocated_bytes'],37740*1024)
        self.assertEqual(result['clients'],1)
        self.assertEqual(result['engines']['render'],0)
    def test_other_device_rejected(self):
        self.assertIsNone(parse('drm-pdev: 0000:01:00.0\ndrm-client-id: 1','0000:00:02.0'))
    def test_capacity_and_regressing_counter(self):
        m=ClientMonitor()
        def client(n): return {'1':{'engines':{'video':n},'capacities':{'video':2},'resident':{},'allocated':{}}}
        m.calculate('gpu',client(1000000000),1)
        self.assertEqual(m.calculate('gpu',client(2000000000),2)['load'],50)
        self.assertEqual(m.calculate('gpu',client(1900000000),3)['load'],0)
        self.assertEqual(m.calculate('gpu',client(2200000000),4)['load'],10)
    def test_unknown_memory_and_clients_not_zero(self):
        result=ClientMonitor().calculate('gpu',{},1)
        self.assertIsNone(result['resident_bytes']); self.assertIsNone(result['load'])
