"""Read-only i915 frequency and non-RC6 activity; not engine utilization."""
import time
from .devices import read
from .drm_clients import ClientMonitor
from pathlib import Path


def value(path):
    try: return int(read(path))
    except ValueError: return None


class IntelMetrics:
    def __init__(self,proc=Path('/proc')):
        self.previous={}
        self.clients=ClientMonitor(proc)

    def sample(self, card, lightweight=False, now=None):
        now=time.monotonic() if now is None else now
        metrics={'freq':None,'load':None,'load_label':'Actividad fuera RC6',
                 'note':'Actividad = tiempo fuera del reposo RC6; no es carga de motores GPU. Temperatura: no expuesta. Memoria compartida con RAM.'}
        if lightweight:
            self.previous.pop(str(card),None)
            self.clients.reset()
            return metrics
        metrics['gt_frequencies']={}
        for path in card.glob('gt/gt*/rps_act_freq_mhz'):
            frequency=value(path)
            if frequency is not None: metrics['gt_frequencies'][path.parent.name]=frequency
        metrics['freq']=max(metrics['gt_frequencies'].values()) if metrics['gt_frequencies'] else value(card/'gt_act_freq_mhz')
        counters={}
        for path in card.glob('gt/gt*/rc6_residency_ms'):
            if value(path.parent/'rc6_enable')!=1: continue
            v=value(path)
            if v is not None: counters[str(path)]=v
        old=self.previous.get(str(card))
        self.previous[str(card)]=(now,counters)
        if old and 0<now-old[0]<=10 and counters and counters.keys()==old[1].keys():
            elapsed=(now-old[0])*1000
            deltas=[v-old[1][k] for k,v in counters.items()]
            if all(0<=d<=elapsed+10 for d in deltas):
                metrics['load']=max(max(0,min(100,100*(1-d/elapsed))) for d in deltas)
        drm=self.clients.sample((card/'device').resolve().name,now)
        metrics['client_metrics']=drm
        metrics['note']='Clientes DRM accesibles de tu usuario; cobertura parcial. Memoria residente sumada: buffers compartidos entre clientes pueden contarse más de una vez.'
        if drm['load'] is not None:
            metrics['load']=drm['load']; metrics['load_label']='Motor más ocupado'
        else:
            metrics['note']+=' Sin dos muestras de motores: el indicador usa actividad fuera RC6.'
        return metrics
