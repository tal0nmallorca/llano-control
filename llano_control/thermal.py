"""Select temperatures from the existing sample; never wake or query a GPU."""
import math
from pathlib import Path

def valid(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and -20<=value<=150

def control_temperature(profile,sample):
    source=profile.get('temperature_source','cpu')
    cpu=sample.get('cpu',{}).get('temp')
    if source in ('cpu','both') and profile.get('sensor'):
        try:cpu=float(Path(profile['sensor']).read_text())/1000
        except (OSError,ValueError):cpu=None
    cpu=cpu if valid(cpu) else None
    selected=profile.get('control_gpu','')
    gpus=[g for g in sample.get('gpus',[]) if not selected or g.get('id')==selected]
    temps=[g['temp'] for g in gpus if valid(g.get('temp'))]
    gpu=max(temps) if temps else None
    if source=='cpu':return cpu,'CPU'
    if source=='gpu':return gpu,'GPU'
    if source!='both':raise ValueError('Unknown temperature source')
    values=[t for t in (cpu,gpu) if t is not None]
    label='CPU + GPU · máxima' if cpu is not None and gpu is not None else 'CPU · GPU sin temperatura' if cpu is not None else 'GPU · CPU sin temperatura'
    return (max(values) if values else None),label
