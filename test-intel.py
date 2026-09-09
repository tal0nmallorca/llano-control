#!/usr/bin/env python3
"""20-second Intel VA-API video workload with per-client DRM evidence. No sudo."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from datetime import datetime


def read(path):
    try: return path.read_text().strip()
    except (OSError, UnicodeError): return None


def collect(card, pid=None):
    frequencies={}
    for pat in ('gt_act_freq_mhz','gt_cur_freq_mhz','gt/gt*/rps_act_freq_mhz','gt/gt*/rc6_residency_ms'):
        for path in card.glob(pat): frequencies[str(path.relative_to(card))]=read(path)
    clients={}
    if pid:
        pci=(card/'device').resolve().name
        for path in (Path('/proc')/str(pid)/'fdinfo').glob('*'):
            text=read(path)
            if not text: continue
            fields=dict(line.split(':',1) for line in text.splitlines() if ':' in line)
            fields={k:v.strip() for k,v in fields.items() if k.startswith(('drm-','i915-'))}
            if fields.get('drm-pdev')!=pci: continue
            ident=fields.get('drm-client-id')
            # Retain one copy per DRM client; preserve FD key if client ID absent.
            clients[ident or 'fd-'+path.name]=fields
    return {'monotonic':time.monotonic(),'frequency_and_rc6':frequencies,'clients':clients}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card',default='card2')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.card.startswith('card') or not args.card[4:].isdigit(): parser.error('Usa cardN')
    card=Path('/sys/class/drm')/args.card
    if read(card/'device/vendor')!='0x8086': parser.error('La tarjeta seleccionada no es Intel')
    render=next((p for p in (card/'device/drm').glob('renderD*') if (Path('/dev/dri')/p.name).exists()),None)
    if render is None: parser.error('No hay render node Intel accesible en /dev/dri. Ejecuta esto en tu terminal local.')
    node=Path('/dev/dri')/render.name
    if not os.access(node,os.R_OK|os.W_OK): parser.error(f'Sin permisos para {node}; ejecuta desde la sesión local con acceso a render.')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: parser.error('Falta ffmpeg: sudo apt install ffmpeg')
    output=args.output or Path.cwd()/('intel-test-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True,exist_ok=False)
    report={'card':args.card,'pci':(card/'device').resolve().name,'render_node':str(node),
            'workload':'VA-API VPP upscale 1080p to 4K; no H.264 encoding; not a full 3D/render benchmark',
            'samples':[],'status':'starting'}
    driver_env=os.environ.copy()
    report['inherited_libva_driver']=driver_env.get('LIBVA_DRIVER_NAME')
    driver_env['LIBVA_DRIVER_NAME']='iHD'
    report['test_libva_driver']='iHD'
    vainfo=shutil.which('vainfo')
    if vainfo:
        with (output/'vainfo.log').open('w') as log:
            try:
                result=subprocess.run([vainfo,'--display','drm','--device',str(node)],env=driver_env,stdout=log,stderr=subprocess.STDOUT,timeout=10)
                report['vainfo_exit_code']=result.returncode
            except (OSError,subprocess.TimeoutExpired) as exc:
                report['vainfo_error']=str(exc)
    proc=None
    def sample(phase,pid=None):
        item=collect(card,pid); item['phase']=phase; report['samples'].append(item)
    try:
        print('Reposo: 3 segundos…',flush=True)
        for _ in range(3): sample('idle'); time.sleep(1)
        command=[ffmpeg,'-hide_banner','-nostdin','-loglevel','info','-vaapi_device',str(node),
                 '-f','lavfi','-i','testsrc2=size=1920x1080:rate=60',
                 '-vf','format=nv12,hwupload,scale_vaapi=w=3840:h=2160:format=nv12,hwdownload,format=nv12',
                 '-c:v','wrapped_avframe','-progress',str(output/'progress.log'),'-f','null','-']
        print('Carga de escalado VA-API Intel: 20 segundos. Ctrl+C para detener.',flush=True)
        with (output/'ffmpeg.log').open('w') as log:
            proc=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=log,env=driver_env)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if proc.poll() is not None:
                    report['status']='workload_failed'; report['exit_code']=proc.returncode
                    print('La carga terminó antes de tiempo. Revisa ffmpeg.log.'); break
                sample('load',proc.pid); time.sleep(1)
            else: report['status']='completed'
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try: proc.wait(timeout=3)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        frames=[]
        for line in (read(output/'progress.log') or '').splitlines():
            if line.startswith('frame='):
                try: frames.append(int(line.split('=',1)[1]))
                except ValueError: pass
        report['frames_processed']=max(frames,default=0)
        if report['status']=='completed' and not report['frames_processed']:
            report['status']='no_frames_processed'
        report['gpu_clients_observed']=any(item['clients'] for item in report['samples'])
        print('Fotogramas procesados:',report['frames_processed'],flush=True)
        print('Recuperación: 3 segundos…',flush=True)
        for _ in range(3): sample('cooldown'); time.sleep(1)
    except KeyboardInterrupt:
        report['status']='interrupted'
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        (output/'samples.json').write_text(json.dumps(report,indent=2))
    print('Resultados:',output.resolve())
    print('Comparte samples.json y ffmpeg.log para validar carga y memoria antes de incorporarlas a la aplicación.')
    return 0 if report['status']=='completed' else 1

if __name__=='__main__': raise SystemExit(main())
