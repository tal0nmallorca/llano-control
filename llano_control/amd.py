"""Read-only CPU sensor selection and AMDGPU telemetry from Linux sysfs."""
import math
import re
from .devices import read


def number(path, scale=1):
    try:
        value=float(read(path))/scale
        return value if math.isfinite(value) else None
    except (ValueError,TypeError): return None


def cpu_temperature(sys):
    # One-shot compatibility helper; Monitor retains a cached reader instead.
    return CpuTemperature(sys).sample(0)


def gpu_metrics(card,lightweight=False):
    dev=card/'device'
    gpu={'id':str(dev.resolve()),'name':(read(dev/'product_name') or 'AMD Radeon')+' · '+card.name,
         'load':None,'temp':None,'freq':None,'power':None,'source':'amdgpu / hwmon',
         'power_label':'Potencia SoC','temperatures':{},'memory_frequency':None,
         'note':'Potencia SoC expuesta por amdgpu; en una APU incluye la CPU. VRAM y GTT son regiones distintas.',
         'memory':{'used':None,'total':None,'load':None}}
    if read(dev/'power/runtime_status') in ('suspended','suspending'):
        gpu['note']='GPU AMD en reposo: no se consultan sensores para evitar despertarla.'
        return gpu
    if not lightweight:
        busy=number(dev/'gpu_busy_percent')
        gpu['load']=busy if busy is not None and 0<=busy<=100 else None
        used,total=number(dev/'mem_info_vram_used',2**30),number(dev/'mem_info_vram_total',2**30)
        gpu['memory']={'used':used,'total':total,'load':min(100,used/total*100) if used is not None and used>=0 and total and total>0 else None}
        gpu['gtt_used']=number(dev/'mem_info_gtt_used',2**30)
        gpu['gtt_total']=number(dev/'mem_info_gtt_total',2**30)
    for hw in sorted((dev/'hwmon').glob('*')):
        if read(hw/'name')!='amdgpu': continue
        for p in sorted(hw.glob('temp*_input')):
            t=number(p,1000)
            if t is not None and -20<=t<=150:
                gpu['temperatures'][read(p.with_name(p.name.replace('_input','_label'))) or p.stem]=t
        t=number(hw/'temp1_input',1000)
        if t is not None and -20<=t<=150: gpu['temp']=t
        if not lightweight:
            gpu['freq']=number(hw/'freq1_input',1e6)
            gpu['memory_frequency']=number(hw/'freq2_input',1e6)
            gpu['power']=number(hw/'power1_average',1e6)
            if gpu['power'] is None: gpu['power']=number(hw/'power1_input',1e6)
    if not lightweight and gpu['freq'] is None:
        for line in read(dev/'pp_dpm_sclk').splitlines():
            if '*' not in line: continue
            match=re.search(r'(\d+)\s*Mhz',line,re.IGNORECASE)
            if match: gpu['freq']=int(match.group(1)); break
    return gpu


class CpuTemperature:
    """Cache sensor identity, never its reading; rediscover once per minute."""
    def __init__(self, sys):
        self.sys=sys; self.next_discovery=0; self.paths=[]; self.intel=False

    def discover(self):
        devices=sorted((self.sys/'class/hwmon').glob('hwmon*'))
        drivers=[(hw,read(hw/'name')) for hw in devices]
        self.intel=any(driver=='coretemp' for _,driver in drivers)
        candidates=[]
        for hw,driver in drivers:
            if driver not in (('coretemp',) if self.intel else ('k10temp','zenpower')): continue
            for path in sorted(hw.glob('temp*_input')):
                label=read(path.with_name(path.name.replace('_input','_label')))
                if self.intel:
                    if label=='Package id 0': candidates.append((0,str(path),path,'coretemp / Package id 0'))
                else:
                    if not label and driver=='k10temp' and path.name=='temp1_input': label='Tctl'
                    if label not in ('Tdie','Tctl'): continue
                    note=' (control térmico; puede incluir offset)' if label=='Tctl' else ''
                    candidates.append((0 if label=='Tdie' else 1,str(path),path,driver+' / '+label+note))
        self.paths=[(path,source) for _,_,path,source in sorted(candidates)]

    def sample(self, now):
        if now>=self.next_discovery:
            self.discover(); self.next_discovery=now+60
        for path,source in self.paths:
            temperature=number(path,1000)
            if temperature is not None and -20<=temperature<=150: return temperature,source
        return None, ('coretemp / Package id 0 (no disponible)' if self.intel else
                      'Sin sensor CPU compatible: coretemp, k10temp o zenpower')
