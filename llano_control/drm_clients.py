"""DRM fdinfo for accessible same-user clients; never claims system-wide coverage."""
import os
import time
from pathlib import Path


def parse(text, pci):
    fields=dict((k,v.strip()) for line in text.splitlines() if ':' in line for k,v in [line.split(':',1)])
    if fields.get('drm-pdev')!=pci or 'drm-client-id' not in fields: return None
    engines={}; capacities={}; resident={}; allocated={}
    for k,v in fields.items():
        parts=v.split()
        if not parts: continue
        try: n=int(parts[0])
        except ValueError: continue
        if n<0: continue
        if k.startswith('drm-engine-capacity-'): capacities[k[20:]]=max(1,n)
        elif k.startswith('drm-engine-') and parts[1:]==['ns']: engines[k[11:]]=n
        elif k.startswith(('drm-resident-','drm-total-')):
            unit=parts[1] if len(parts)>1 else 'B'
            scale={'B':1,'KiB':1024,'MiB':1048576}.get(unit)
            if scale is None: continue
            target=resident if k.startswith('drm-resident-') else allocated
            target[k.split('-',2)[2]]=n*scale
    return fields['drm-client-id'],{'engines':engines,'capacities':capacities,'resident':resident,'allocated':allocated}


class ClientMonitor:
    def __init__(self,proc=Path('/proc')):
        self.proc=proc; self.paths={}; self.next_scan=0; self.previous={}

    def reset(self): self.previous.clear()

    def sample(self,pci,now=None):
        now=time.monotonic() if now is None else now
        if now>=self.next_scan:
            paths=[]; deadline=time.monotonic()+.05
            for process in self.proc.glob('[0-9]*'):
                if time.monotonic()>deadline: break
                try:
                    if process.stat().st_uid!=os.getuid(): continue
                    for path in (process/'fdinfo').iterdir():
                        if time.monotonic()>deadline: break
                        try:
                            # Only retain DRM fdinfo paths, not process command lines.
                            if 'drm-driver:' in path.read_text(): paths.append(path)
                        except OSError: pass
                except OSError: continue
            self.paths={str(p):p for p in paths}; self.next_scan=now+5
        clients={}
        for path in list(self.paths.values()):
            try: item=parse(path.read_text(),pci)
            except OSError: self.paths.pop(str(path),None); continue
            if item: clients[item[0]]=item[1]
        return self.calculate(pci,clients,now)

    def calculate(self,pci,clients,now):
        previous=self.previous.get(pci)
        engines={}; capacity={}; comparable=False
        if previous and 0<now-previous[0]<=10:
            dt=(now-previous[0])*1e9
            for ident,client in clients.items():
                old=previous[1].get(ident)
                if old is None: continue
                for engine,counter in list(client['engines'].items()):
                    if engine not in old['engines']: continue
                    comparable=True
                    baseline=old['engines'][engine]
                    client['engines'][engine]=max(counter,baseline)
                    engines[engine]=engines.get(engine,0)+max(0,counter-baseline)/dt*100
                    capacity[engine]=max(capacity.get(engine,1),client['capacities'].get(engine,1))
        engines={k:min(100,v/capacity[k]) for k,v in engines.items()}
        resident=[sum(c['resident'].values()) for c in clients.values() if c['resident']]
        allocated=[sum(c['allocated'].values()) for c in clients.values() if c['allocated']]
        self.previous[pci]=(now,clients)
        return {'load':max(engines.values()) if comparable and engines else None,'engines':engines,
                'resident_bytes':sum(resident) if resident else None,
                'allocated_bytes':sum(allocated) if allocated else None,'clients':len(clients)}
