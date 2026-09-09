"""Read-only telemetry. None means unavailable, never an invented zero."""
import csv
import math
import shutil
import subprocess
import time
from pathlib import Path
from .devices import read
from .power import PackagePower
from .intel import IntelMetrics
from .amd import CpuTemperature, gpu_metrics


def numeric(value, scale=1):
    try:
        result = float(value) / scale
        return result if math.isfinite(result) else None
    except (TypeError, ValueError): return None


def cpu_times(text):
    fields = next(line for line in text.splitlines() if line.startswith('cpu ')).split()[1:]
    values = list(map(int, fields[:8]))  # guest times already included in user/nice
    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)


def cpu_usage(previous, current):
    if previous is None: return None
    total, idle = current[0]-previous[0], current[1]-previous[1]
    if total <= 0 or idle < 0: return None
    return max(0, min(100, 100*(total-idle)/total))


def memory(text):
    values = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) > 1: values[fields[0].rstrip(':')] = numeric(fields[1])
    total, available = values.get('MemTotal'), values.get('MemAvailable')
    if not total or available is None: return {'used': None, 'total': None, 'load': None}
    used = max(0, total-available)
    return {'used': used/1048576, 'total': total/1048576, 'load': used/total*100}


def parse_nvidia(text):
    rows=[]
    for fields in csv.reader(text.splitlines(), skipinitialspace=True):
        if len(fields) != 9: continue
        index, name, load, temp, freq, power, used, total, uuid = fields
        used, total = numeric(used,1024), numeric(total,1024)
        rows.append({'id': uuid.strip(), 'name': name.strip(), 'load': numeric(load),
                     'temp': numeric(temp), 'freq': numeric(freq), 'power': numeric(power),
                     'memory': {'used': used, 'total': total, 'load': used/total*100 if used is not None and total else None},
                     'source': 'nvidia-smi'})
    return rows


def parse_nvidia_temperature(text):
    rows=[]
    for fields in csv.reader(text.splitlines(), skipinitialspace=True):
        if len(fields)!=4: continue
        _,name,temp,uuid=fields
        rows.append({'id':uuid.strip(),'name':name.strip(),'temp':numeric(temp),
                     'load':None,'freq':None,'power':None,'memory':{},'source':'nvidia-smi'})
    return rows


class Monitor:
    def __init__(self, proc=Path('/proc'), sys=Path('/sys')):
        self.proc, self.sys = proc, sys
        self.previous = None
        self.nvidia = shutil.which('nvidia-smi')
        self.nvidia_retry=0
        self.nvidia_error=''
        self.nvidia_ids=set()
        self.cpu_name='CPU'
        self.package_power=PackagePower(sys)
        self.intel=IntelMetrics(proc)
        self.cpu_temperature=CpuTemperature(sys)
        self.next_discovery=0; self.nvidia_devices=[]; self.cards=[]

    def discover(self, now):
        if now<self.next_discovery: return
        self.nvidia_devices=[p for p in (self.sys/'bus/pci/devices').glob('*')
                             if read(p/'vendor')=='0x10de' and read(p/'class').startswith('0x03')]
        self.cards=[]
        for card in sorted((self.sys/'class/drm').glob('card[0-9]*')):
            if '-' in card.name: continue
            vendor=read(card/'device/vendor')
            if vendor in ('0x1002','0x8086'): self.cards.append((card,vendor))
        self.next_discovery=now+30

    def sample(self, lightweight=False, display_gpu=None):
        errors=[]
        now_monotonic=time.monotonic(); self.discover(now_monotonic)
        cpu={'name':'CPU', 'load':None, 'temp':None, 'freq':None, 'power':None, 'temp_source':'Sin sensor CPU compatible'}
        try:
            if lightweight: raise StopIteration
            now=cpu_times(read(self.proc/'stat')); cpu['load']=cpu_usage(self.previous,now); self.previous=now
        except (StopIteration,ValueError,IndexError): self.previous=None
        info=read(self.proc/'cpuinfo') if not lightweight else ''
        lines=info.splitlines()
        if self.cpu_name=='CPU':
            self.cpu_name=next((line.split(':',1)[1].strip() for line in lines if line.startswith('model name')), 'CPU')
        cpu['name']=self.cpu_name
        frequencies=[numeric(line.split(':',1)[1]) for line in lines if line.startswith('cpu MHz')]
        frequencies=[v for v in frequencies if v is not None]
        if frequencies: cpu['freq']=sum(frequencies)/len(frequencies)
        if lightweight:
            self.package_power.reset()
        else:
            cpu['power']=self.package_power.sample()
        cpu['power_source']=self.package_power.status
        cpu['temp'],cpu['temp_source']=self.cpu_temperature.sample(now_monotonic)
        gpus=[]
        suspended=any(read(p/'power/runtime_status') in ('suspended','suspending') for p in self.nvidia_devices)
        if self.nvidia and suspended:
            errors.append('NVIDIA en reposo: no se consulta para evitar despertarla')
        elif self.nvidia and time.monotonic()<self.nvidia_retry:
            errors.append(self.nvidia_error)
        elif self.nvidia:
            try:
                nvidia_light=lightweight or (display_gpu is not None and bool(self.nvidia_ids) and display_gpu not in self.nvidia_ids)
                query='index,name,temperature.gpu,uuid' if nvidia_light else 'index,name,utilization.gpu,temperature.gpu,clocks.gr,power.draw,memory.used,memory.total,uuid'
                result=subprocess.run([self.nvidia,'--query-gpu='+query,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
                if result.returncode==0:
                    gpus=parse_nvidia_temperature(result.stdout) if nvidia_light else parse_nvidia(result.stdout)
                    self.nvidia_ids={g['id'] for g in gpus}
                else: errors.append('NVIDIA: el controlador no permite consultar la GPU')
            except (OSError,subprocess.TimeoutExpired): errors.append('NVIDIA: consulta no disponible o agotó el tiempo de espera')
        if self.nvidia and errors and not suspended and time.monotonic()>=self.nvidia_retry:
            self.nvidia_error=errors[-1]; self.nvidia_retry=time.monotonic()+60
        for card,vendor in self.cards:
            dev=card/'device'
            gpu_light=lightweight or (display_gpu is not None and str(dev.resolve())!=display_gpu)
            if vendor=='0x1002':
                gpus.append(gpu_metrics(card,gpu_light))
                continue
            gpu={'id':str(dev.resolve()),'name':('AMD' if vendor=='0x1002' else 'Intel')+' · '+card.name,
                 'load':None if gpu_light else numeric(read(dev/'gpu_busy_percent')),'temp':None,'freq':None,'power':None,
                 'source':'DRM / hwmon'}
            used,total=(None,None) if gpu_light else (numeric(read(dev/'mem_info_vram_used'),2**30),numeric(read(dev/'mem_info_vram_total'),2**30))
            gpu['memory']={'used':used,'total':total,'load':used/total*100 if used is not None and total else None}
            for hw in sorted((dev/'hwmon').glob('*')):
                gpu['temp']=numeric(read(hw/'temp1_input'),1000)
                if not gpu_light:
                    gpu['freq']=numeric(read(hw/'freq1_input'),1e6)
                    gpu['power']=numeric(read(hw/'power1_average'),1e6)
            if vendor=='0x8086':
                intel=self.intel.sample(card,lightweight=gpu_light)
                if gpu['freq'] is None: gpu['freq']=intel['freq']
                if gpu['load'] is None:
                    gpu['load']=intel['load']; gpu['load_label']=intel['load_label']
                gpu['note']=intel['note']
                gpu['name']='Intel iGPU · '+card.name
                gpu['memory']['shared']=True
                gpu['gt_frequencies']=intel.get('gt_frequencies',{})
                gpu['client_metrics']=intel.get('client_metrics',{})
            gpus.append(gpu)
        return {'cpu':cpu,'gpus':gpus,'ram':memory(read(self.proc/'meminfo') if not lightweight else ''),'errors':errors}
