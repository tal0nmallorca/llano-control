import tempfile
import unittest
from pathlib import Path
from llano_control.power import PackagePower

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.domain=self.root/'devices/virtual/powercap/intel-rapl/intel-rapl:0'
        self.domain.mkdir(parents=True)
        (self.domain/'name').write_text('package-0')
        (self.domain/'max_energy_range_uj').write_text('1000000000')
        self.energy(10000000); self.reader=PackagePower(self.root)
    def energy(self,value): (self.domain/'energy_uj').write_text(str(value))
    def test_watts(self):
        self.assertIsNone(self.reader.sample(1)); self.energy(38000000)
        self.assertEqual(self.reader.sample(2),28)
    def test_deduplicate_mmio(self):
        other=self.root/'devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0'; other.mkdir(parents=True)
        (other/'name').write_text('package-0'); (other/'energy_uj').write_text('100')
        self.reader.discover(); self.assertEqual(self.reader.domains,[self.domain])
    def test_wrap(self):
        self.energy(990000000); self.reader.sample(1); self.energy(10000000)
        self.assertEqual(self.reader.sample(2),20)
    def test_reset_and_pause(self):
        self.reader.sample(1); self.energy(1); self.assertIsNone(self.reader.sample(2))
        self.energy(1000); self.assertIsNone(self.reader.sample(20))
    def test_unreadable_not_zero(self):
        self.reader.sample(1); (self.domain/'energy_uj').unlink()
        self.assertIsNone(self.reader.sample(2))
    def test_hidden_resets_baseline(self):
        self.reader.sample(1); self.reader.reset(); self.energy(38000000)
        self.assertIsNone(self.reader.sample(2))
