import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import subprocess
from llano_control.telemetry import cpu_times,cpu_usage,memory,parse_nvidia,Monitor

class TelemetryTests(unittest.TestCase):
    def test_cpu_delta_not_lifetime(self):
        a=cpu_times('cpu 100 0 100 800 0 0 0 0 50 0')
        b=cpu_times('cpu 120 0 110 870 0 0 0 0 60 0')
        self.assertEqual(cpu_usage(a,b),30)
        self.assertIsNone(cpu_usage(None,b))
        self.assertIsNone(cpu_usage(b,a))
    def test_memory_available_not_free(self):
        m=memory('MemTotal: 1048576 kB\nMemAvailable: 262144 kB\nMemFree: 1 kB')
        self.assertEqual(m,{'used':.75,'total':1,'load':75})
        self.assertIsNone(memory('')['load'])
    def test_multi_gpu_and_na(self):
        rows=parse_nvidia('0, RTX 1, 30, 55, 1500, 100, 1024, 8192, GPU-a\n1, RTX 2, [N/A], [N/A], [N/A], [N/A], 0, 8192, GPU-b')
        self.assertEqual(rows[0]['memory']['load'],12.5)
        self.assertIsNone(rows[1]['load'])
        self.assertEqual(rows[1]['memory']['used'],0)
    def test_missing_driver_preserves_cpu_and_ram(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); proc=root/'proc'; proc.mkdir()
            (proc/'stat').write_text('cpu 100 0 0 100 0 0 0 0')
            (proc/'meminfo').write_text('MemTotal: 1048576 kB\nMemAvailable: 524288 kB')
            hw=root/'sys/class/hwmon/hwmon0'; hw.mkdir(parents=True)
            (hw/'name').write_text('coretemp'); (hw/'temp1_input').write_text('62000'); (hw/'temp1_label').write_text('Package id 0')
            mon=Monitor(proc,root/'sys'); mon.nvidia='/test/nvidia-smi'
            with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('nvidia-smi',2)):
                result=mon.sample()
            self.assertEqual(result['cpu']['temp'],62)
            self.assertEqual(result['ram']['load'],50)
            self.assertEqual(result['gpus'],[])
            self.assertTrue(result['errors'])
    def test_lightweight_skips_proc_reads(self):
        from llano_control.devices import read as actual_read
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); mon=Monitor(root/'proc',root/'sys'); mon.nvidia=None
            paths=[]
            def tracked(path): paths.append(str(path)); return actual_read(path)
            with patch('llano_control.telemetry.read',side_effect=tracked): mon.sample(lightweight=True)
            self.assertFalse(any('/proc/' in path for path in paths))
    def test_suspended_nvidia_is_not_queried(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); dev=root/'sys/bus/pci/devices/0000:01:00.0'; (dev/'power').mkdir(parents=True)
            (dev/'vendor').write_text('0x10de'); (dev/'class').write_text('0x030000')
            (dev/'power/runtime_status').write_text('suspended')
            mon=Monitor(root/'proc',root/'sys'); mon.nvidia='/test/nvidia-smi'
            with patch('subprocess.run') as run: result=mon.sample(lightweight=True)
            run.assert_not_called(); self.assertIn('reposo',result['errors'][0])
    def test_failed_nvidia_backs_off(self):
        with tempfile.TemporaryDirectory() as d:
            mon=Monitor(Path(d)/'proc',Path(d)/'sys'); mon.nvidia='/test/nvidia-smi'
            with patch('subprocess.run',return_value=SimpleResult()) as run:
                mon.sample(); mon.sample()
            self.assertEqual(run.call_count,1)

    def test_package_zero_not_hottest_core(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); hw=root/'sys/class/hwmon/hwmon42'; hw.mkdir(parents=True)
            (hw/'name').write_text('coretemp')
            for i,(label,temp) in enumerate([('Core 0',90000),('Package id 1',85000),('Package id 0',60000)],1):
                (hw/f'temp{i}_label').write_text(label); (hw/f'temp{i}_input').write_text(str(temp))
            mon=Monitor(root/'proc',root/'sys'); mon.nvidia=None
            self.assertEqual(mon.sample()['cpu']['temp'],60)
            (hw/'temp3_input').unlink()
            self.assertIsNone(mon.sample()['cpu']['temp'])

class SimpleResult:
    returncode=1
    stdout=''
