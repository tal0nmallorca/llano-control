import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from llano_control.amd import CpuTemperature
from llano_control.telemetry import Monitor

class EfficiencyTests(unittest.TestCase):
    def sensor(self,root):
        hw=root/'class/hwmon/hwmon0'; hw.mkdir(parents=True)
        (hw/'name').write_text('coretemp')
        (hw/'temp1_label').write_text('Package id 0')
        (hw/'temp1_input').write_text('51000')
        return hw

    def test_sensor_cache_reads_live_values_and_rediscovers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); hw=self.sensor(root); sensor=CpuTemperature(root)
            with patch.object(sensor,'discover',wraps=sensor.discover) as discover:
                self.assertEqual(sensor.sample(0)[0],51)
                (hw/'temp1_input').write_text('62000')
                self.assertEqual(sensor.sample(2)[0],62)
                (hw/'temp1_input').unlink()
                self.assertIsNone(sensor.sample(4)[0])
                discover.assert_called_once()
                (hw/'temp2_label').write_text('Package id 0'); (hw/'temp2_input').write_text('53000')
                self.assertEqual(sensor.sample(60)[0],53)
                self.assertEqual(discover.call_count,2)

    def test_topology_refresh_detects_new_card(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); mon=Monitor(root/'proc',root/'sys'); mon.nvidia=None
            mon.discover(0); self.assertEqual(mon.cards,[])
            dev=root/'sys/class/drm/card2/device'; dev.mkdir(parents=True)
            (dev/'vendor').write_text('0x8086')
            mon.discover(2); self.assertEqual(mon.cards,[])
            mon.discover(30); self.assertEqual(mon.cards,[(dev.parent,'0x8086')])

    def test_hidden_nvidia_queries_temperature_only(self):
        with tempfile.TemporaryDirectory() as d:
            mon=Monitor(Path(d)/'proc',Path(d)/'sys'); mon.nvidia='/test/nvidia-smi'
            with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='0, NVIDIA RTX, 51, GPU-a')) as run:
                sample=mon.sample(lightweight=True)
            query=run.call_args.args[0][1]
            self.assertEqual(query,'--query-gpu=index,name,temperature.gpu,uuid')
            self.assertEqual(sample['gpus'][0]['temp'],51)
            self.assertIsNone(sample['gpus'][0]['load'])

    def test_hidden_intel_skips_load_clock_memory_and_power(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); dev=root/'sys/class/drm/card2/device'; hw=dev/'hwmon/hwmon1'; hw.mkdir(parents=True)
            (dev/'vendor').write_text('0x8086')
            mon=Monitor(root/'proc',root/'sys'); mon.nvidia=None
            from llano_control.devices import read
            with patch('llano_control.telemetry.read',wraps=read) as reader:
                mon.sample(lightweight=True)
            names={call.args[0].name for call in reader.call_args_list}
            self.assertFalse(names & {'gpu_busy_percent','freq1_input','power1_average','mem_info_vram_used','mem_info_vram_total'})

    def test_gauges_skip_visually_identical_updates(self):
        from llano_control.gui import Gauge
        gauge=SimpleNamespace(title='Carga',queue_draw=Mock())
        Gauge.update(gauge,50.1); Gauge.update(gauge,50.2)
        gauge.queue_draw.assert_called_once()
        Gauge.update(gauge,None); self.assertEqual(gauge.queue_draw.call_count,2)
        Gauge.update(gauge,None); self.assertEqual(gauge.queue_draw.call_count,2)

    def test_tray_only_sends_changed_display_values(self):
        from llano_control.gui import App
        app=SimpleNamespace(language=Mock(),tray=Mock())
        app.language.get_active_id.return_value='es'; app.tray.poll.return_value=None
        app.tray.stdin.fileno.return_value=5
        with patch('llano_control.gui.os.write') as write:
            App.send_tray(app,{'cpu':50.1,'gpu':51.2})
            App.send_tray(app,{'cpu':50.2,'gpu':51.3})
            write.assert_called_once()
            app.language.get_active_id.return_value='en'
            App.send_tray(app,{'cpu':50.2,'gpu':51.3})
            self.assertEqual(write.call_count,2)
