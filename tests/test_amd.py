import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from llano_control.amd import cpu_temperature,gpu_metrics

class AMDTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
    def write(self,path,value):
        p=self.root/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(str(value))
    def sensor(self,driver,label,temp,index=1):
        self.write('class/hwmon/hwmon0/name',driver)
        self.write(f'class/hwmon/hwmon0/temp{index}_label',label)
        self.write(f'class/hwmon/hwmon0/temp{index}_input',temp)
    def test_tdie_preferred_to_hotter_tctl_and_ccd(self):
        self.sensor('k10temp','Tctl',85000);self.sensor('k10temp','Tdie',65000,2);self.sensor('k10temp','Tccd1',90000,3)
        self.assertEqual(cpu_temperature(self.root),(65,'k10temp / Tdie'))
    def test_tctl_fallback_explicit(self):
        self.sensor('k10temp','Tctl',72000)
        t,label=cpu_temperature(self.root);self.assertEqual(t,72);self.assertIn('offset',label)
    def test_legacy_unlabelled_k10temp(self):
        self.write('class/hwmon/hwmon0/name','k10temp');self.write('class/hwmon/hwmon0/temp1_input',45000)
        self.assertEqual(cpu_temperature(self.root)[0],45)
    def test_intel_preference_preserved(self):
        self.sensor('coretemp','Core 0',90000)
        self.assertIsNone(cpu_temperature(self.root)[0])
        self.sensor('coretemp','Package id 0',55000,2)
        self.assertEqual(cpu_temperature(self.root),(55,'coretemp / Package id 0'))
    def gpu_fixture(self):
        base='card0/device/'
        for key,val in {'power/runtime_status':'active','product_name':'Test Radeon','gpu_busy_percent':75,'mem_info_vram_used':2**30,'mem_info_vram_total':8*2**30,'mem_info_gtt_used':2**29,'mem_info_gtt_total':16*2**30,'hwmon/hwmon3/name':'amdgpu','hwmon/hwmon3/temp1_input':65000,'hwmon/hwmon3/temp1_label':'edge','hwmon/hwmon3/temp2_input':85000,'hwmon/hwmon3/temp2_label':'junction','hwmon/hwmon3/freq1_input':2400000000,'hwmon/hwmon3/freq2_input':1000000000,'hwmon/hwmon3/power1_average':120000000}.items():self.write(base+key,val)
        return self.root/'card0'
    def test_radeon_units_and_regions(self):
        gpu=gpu_metrics(self.gpu_fixture())
        self.assertEqual(gpu['load'],75);self.assertEqual(gpu['temp'],65)
        self.assertEqual(gpu['temperatures']['junction'],85)
        self.assertEqual(gpu['freq'],2400);self.assertEqual(gpu['power'],120)
        self.assertEqual(gpu['memory']['load'],12.5);self.assertEqual(gpu['gtt_used'],.5)
        self.assertEqual(gpu['power_label'],'Potencia SoC')
    def test_sleep_avoids_sensor_access(self):
        card=self.gpu_fixture();self.write('card0/device/power/runtime_status','suspended')
        with patch('llano_control.amd.number',side_effect=AssertionError('sensor access')):gpu=gpu_metrics(card)
        self.assertIsNone(gpu['temp']);self.assertIsNone(gpu['load'])
    def test_lightweight_only_temperatures(self):
        gpu=gpu_metrics(self.gpu_fixture(),True)
        self.assertEqual(gpu['temp'],65);self.assertIsNone(gpu['freq']);self.assertIsNone(gpu['power']);self.assertIsNone(gpu['load'])
    def test_power_and_frequency_fallbacks(self):
        card=self.gpu_fixture()
        (card/'device/hwmon/hwmon3/power1_average').unlink();(card/'device/hwmon/hwmon3/freq1_input').unlink()
        self.write('card0/device/hwmon/hwmon3/power1_input',45000000)
        self.write('card0/device/pp_dpm_sclk','0: 500Mhz\n1: 1500Mhz *')
        gpu=gpu_metrics(card);self.assertEqual(gpu['power'],45);self.assertEqual(gpu['freq'],1500)
