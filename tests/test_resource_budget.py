import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace
from llano_control.telemetry import Monitor
from llano_control.drm_clients import ClientMonitor

class ResourceBudgetTests(unittest.TestCase):
    def test_unselected_intel_keeps_temperature_without_client_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card=root/'sys/class/drm/card2';hw=card/'device/hwmon/hwmon1'
            hw.mkdir(parents=True);(card/'device/vendor').write_text('0x8086');(hw/'temp1_input').write_text('51000')
            monitor=Monitor(root/'proc',root/'sys');monitor.nvidia=None
            with patch.object(monitor.intel.clients,'sample') as scan:
                sample=monitor.sample(display_gpu='GPU-nvidia')
            gpu=sample['gpus'][0]
            self.assertEqual(gpu['temp'],51)
            self.assertIsNone(gpu['load']);self.assertIsNone(gpu['freq'])
            scan.assert_not_called()

    def test_switching_to_intel_restores_detailed_readings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);card=root/'sys/class/drm/card2';dev=card/'device';dev.mkdir(parents=True)
            (dev/'vendor').write_text('0x8086');(card/'gt_act_freq_mhz').write_text('900')
            monitor=Monitor(root/'proc',root/'sys');monitor.nvidia=None
            monitor.sample(display_gpu='GPU-nvidia')
            with patch.object(monitor.intel.clients,'sample',return_value={'load':25,'engines':{},'resident_bytes':None,'allocated_bytes':None,'clients':1}) as scan:
                gpu=monitor.sample(display_gpu=str(dev.resolve()))['gpus'][0]
            scan.assert_called_once();self.assertEqual(gpu['freq'],900);self.assertEqual(gpu['load'],25)

    def test_unselected_nvidia_uses_temperature_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);monitor=Monitor(root/'proc',root/'sys');monitor.nvidia='/mock/nvidia-smi';monitor.nvidia_ids={'GPU-a'}
            with patch('llano_control.telemetry.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='0,NVIDIA,52,GPU-a')) as run:
                sample=monitor.sample(display_gpu='/intel/device')
            self.assertIn('--query-gpu=index,name,temperature.gpu,uuid',run.call_args.args[0])
            self.assertEqual(sample['gpus'][0]['temp'],52)

    def test_drm_discovery_does_not_read_unrelated_fdinfo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);process=root/'123';(process/'fdinfo').mkdir(parents=True);(process/'fd').mkdir()
            for i in range(200):
                (process/'fd'/str(i)).symlink_to('/tmp/unrelated')
                (process/'fdinfo'/str(i)).write_text('not drm')
            (process/'fd'/'200').symlink_to('/dev/dri/renderD129')
            (process/'fdinfo'/'200').write_text('drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 1\ndrm-engine-render: 20 ns\n')
            original=Path.read_text;reads=[]
            def read(path,*args,**kw):
                reads.append(path);return original(path,*args,**kw)
            with patch.object(Path,'read_text',read):
                sample=ClientMonitor(root).sample('0000:00:02.0',0)
            self.assertEqual(sample['clients'],1)
            self.assertEqual(set(reads),{process/'fdinfo'/'200'})
