import copy,math,tempfile,unittest
from pathlib import Path
from llano_control.core import DEFAULT,Preview,validate,effective_curve
from llano_control.fan import FanController
from llano_control.thermal import control_temperature

class ThermalTests(unittest.TestCase):
    def profile(self,source='cpu'):
        p=copy.deepcopy(DEFAULT['profiles']['Equilibrado']);p['temperature_source']=source;p['mode']='Medium';return p
    def sample(self):return {'cpu':{'temp':55},'gpus':[{'id':'intel','temp':60},{'id':'nvidia','temp':80}]}
    def test_cpu_gpu_and_maximum(self):
        for source,expected in [('cpu',55),('gpu',80),('both',80)]:
            self.assertEqual(control_temperature(self.profile(source),self.sample())[0],expected)
    def test_explicit_gpu_never_silently_uses_another(self):
        p=self.profile('gpu');p['control_gpu']='intel'
        self.assertEqual(control_temperature(p,self.sample())[0],60)
        p['control_gpu']='missing';self.assertIsNone(control_temperature(p,self.sample())[0])
    def test_combined_available_fallback_and_invalid_values(self):
        p=self.profile('both')
        for bad in (None,float('nan'),float('inf'),200,True):
            sample={'cpu':{'temp':55},'gpus':[{'id':'gpu','temp':bad}]}
            temp,label=control_temperature(p,sample);self.assertEqual(temp,55);self.assertIn('GPU sin',label)
        self.assertIsNone(control_temperature(p,{})[0])
    def test_gpu_only_ignores_cpu_override(self):
        p=self.profile('gpu');p['sensor']='/does/not/exist'
        self.assertEqual(control_temperature(p,self.sample())[0],80)
    def test_cpu_override_combines_with_selected_gpu(self):
        with tempfile.TemporaryDirectory() as d:
            sensor=Path(d)/'temp';sensor.write_text('90000')
            p=self.profile('both');p['sensor']=str(sensor)
            self.assertEqual(control_temperature(p,self.sample())[0],90)
    def test_sources_reach_all_curves(self):
        for mode in ('Low','Medium','High','Custom','Manual'):
            p=self.profile('gpu');p.update(mode=mode,manual_thermal=True,rpm=2000)
            low=Preview().calculate(p,30);high=Preview().calculate(p,90)
            self.assertGreater(high,low)
            c=FanController(p)
            with self.assertRaises(ValueError):c.plan(None,0)
    def test_manual_thermal_and_legacy_fixed(self):
        p=self.profile();p.update(mode='Manual',rpm=2000,manual_thermal=True)
        self.assertEqual(effective_curve(p),((30,300),(90,2000)))
        self.assertEqual(Preview().calculate(p,30),300)
        self.assertEqual(Preview().calculate(p,90),2000)
        p['manual_thermal']=False;self.assertEqual(Preview().calculate(p,None),2000)
    def test_profile_validation_and_legacy_default(self):
        data=copy.deepcopy(DEFAULT);validate(data)
        p=data['profiles'][data['active']];p.update(temperature_source='both',control_gpu='GPU-uuid',manual_thermal=True);validate(data)
        p['temperature_source']='unknown'
        with self.assertRaises(ValueError):validate(data)

    def test_renumbered_hwmon_drives_changing_targets(self):
        with tempfile.TemporaryDirectory() as d:
            device=Path(d)/'coretemp.0/hwmon'
            current=device/'hwmon7/temp1_input';current.parent.mkdir(parents=True)
            current.write_text('40000')
            p=self.profile('both');p.update(mode='High',sensor=str(device/'hwmon6/temp1_input'))
            controller=FanController(p)
            sample={'cpu':{'temp':40},'gpus':[{'id':'nvidia','temp':35}]}
            first=controller.plan(control_temperature(p,sample)[0],0)
            controller.completed({'power':True})
            current.write_text('80000')
            second=controller.plan(control_temperature(p,sample)[0],6)
            self.assertGreater(second['percent'],first['percent'])
            self.assertFalse(second['take_control'])

    def test_sensor_rebind_never_crosses_devices_or_ambiguous_channels(self):
        from llano_control.thermal import resolve_sensor_path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'coretemp.0/hwmon/hwmon6/temp1_input'
            other=root/'coretemp.1/hwmon/hwmon7/temp1_input';other.parent.mkdir(parents=True);other.write_text('95000')
            self.assertEqual(resolve_sensor_path(str(old)),old)
            resolve_sensor_path.cache_clear()
            for i in (7,8):
                p=old.parent.parent/f'hwmon{i}/temp1_input';p.parent.mkdir(parents=True);p.write_text('45000')
            self.assertEqual(resolve_sensor_path(str(old)),old)
