import tempfile
import unittest
from pathlib import Path
from llano_control.intel import IntelMetrics

class IntelTests(unittest.TestCase):
    def test_frequency_and_rc6(self):
        with tempfile.TemporaryDirectory() as d:
            card=Path(d); gt=card/'gt/gt0'; gt.mkdir(parents=True)
            (card/'gt_act_freq_mhz').write_text('550')
            (gt/'rc6_enable').write_text('1'); counter=gt/'rc6_residency_ms'; counter.write_text('100')
            m=IntelMetrics(); self.assertIsNone(m.sample(card,now=1)['load'])
            counter.write_text('850'); result=m.sample(card,now=2)
            self.assertEqual(result['freq'],550); self.assertEqual(result['load'],25)
            self.assertEqual(result['load_label'],'Actividad fuera RC6')
            self.assertIsNone(m.sample(card,lightweight=True,now=3)['load'])
    def test_missing_is_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            data=IntelMetrics().sample(Path(d))
            self.assertIsNone(data['load']); self.assertIsNone(data['freq'])
    def test_zero_frequency_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'gt_act_freq_mhz').write_text('0')
            self.assertEqual(IntelMetrics().sample(p)['freq'],0)
    def test_per_gt_overrides_misleading_zero(self):
        with tempfile.TemporaryDirectory() as d:
            card=Path(d); (card/'gt_act_freq_mhz').write_text('0')
            for name,frequency in [('gt0',550),('gt1',1150)]:
                gt=card/'gt'/name; gt.mkdir(parents=True)
                (gt/'rps_act_freq_mhz').write_text(str(frequency))
            result=IntelMetrics().sample(card)
            self.assertEqual(result['freq'],1150)
            self.assertEqual(result['gt_frequencies'],{'gt0':550,'gt1':1150})
