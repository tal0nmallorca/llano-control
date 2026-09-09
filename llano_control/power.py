"""CPU package average power from read-only RAPL energy counters (microjoules)."""
import time
from pathlib import Path
from .devices import read


def integer(path):
    try: return int(path.read_text().strip())
    except (OSError, ValueError): return None


class PackagePower:
    def __init__(self, sys=Path('/sys')):
        self.sys=sys
        self.domains=[]
        self.previous={}
        self.next_discovery=0
        self.status='Esperando dos lecturas de energía CPU'

    def reset(self):
        self.previous.clear()

    def discover(self):
        # Prefer MSR-backed RAPL over MMIO; both may expose the same package.
        found={}
        root=self.sys/'devices/virtual/powercap'
        paths=sorted(root.glob('**/name'),key=lambda p: ('mmio' in str(p), str(p)))
        for name_file in paths:
            name=read(name_file)
            if not name.startswith('package-'): continue
            domain=name_file.parent
            if name not in found and (domain/'energy_uj').exists(): found[name]=domain
        self.domains=list(found.values())

    def sample(self, now=None):
        now=time.monotonic() if now is None else now
        if now>=self.next_discovery:
            self.discover(); self.next_discovery=now+60
        if not self.domains:
            self.status='El kernel no expone energía del paquete CPU (RAPL)'
            self.reset(); return None
        total=0.0; ready=True
        for domain in self.domains:
            energy=integer(domain/'energy_uj'); limit=integer(domain/'max_energy_range_uj')
            if energy is None or energy<0:
                self.previous.pop(domain,None)
                self.status='Energía CPU no legible: comprueba permisos de lectura RAPL'
                ready=False; continue
            previous=self.previous.get(domain)
            self.previous[domain]=(now,energy)
            if previous is None:
                self.status='Esperando la segunda lectura de energía CPU'; ready=False; continue
            elapsed=now-previous[0]; delta=energy-previous[1]
            if elapsed<=0 or elapsed>10:
                self.status='Reiniciando medición tras pausa'; ready=False; continue
            if delta<0:
                # A reset and rollover are indistinguishable in general. Only accept
                # rollover near the boundary; discard other decreases conservatively.
                if limit and previous[1]>.9*limit and energy<.1*limit:
                    delta+=limit
                else:
                    self.status='Contador CPU reiniciado'; ready=False; continue
            total+=delta/1_000_000/elapsed
        if ready:
            self.status='Potencia media del paquete CPU · RAPL (Δenergía / Δtiempo)'
            return total
        return None
