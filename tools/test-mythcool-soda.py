#!/usr/bin/env python3
"""Back up MythCool, enable its Llano HID with Soda, and log a bounded launch."""
import argparse
import contextlib
import datetime
import fcntl
import signal
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import yaml

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llano_control.devices import inventory

APP='com.usebottles.bottles'
RUNNER='soda-11.0-9'
DEVICE='0x374A/0xB101'
DEBUG='-all,+timestamp,+pid,+hid,+plugplay,+winebus'
LIMIT=16*1024*1024


def load_config(path):
    value=yaml.safe_load(path.read_text())
    if not isinstance(value,dict): raise ValueError('Configuración de botella inválida')
    return value


def save_config(path,value):
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as stream:
            name=stream.name; yaml.safe_dump(value,stream,allow_unicode=True,sort_keys=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def enable_hid(config):
    params=config.setdefault('Parameters',{})
    devices=params.setdefault('hidraw_devices',[])
    if not isinstance(devices,list): raise ValueError('hidraw_devices no es una lista')
    if DEVICE not in devices: devices.append(DEVICE)


def restore_debug(config,original):
    env=config.setdefault('Environment_Variables',{})
    if 'WINEDEBUG' in original: env['WINEDEBUG']=original['WINEDEBUG']
    else: env.pop('WINEDEBUG',None)


def prefix_processes(bottle, proc_root=Path('/proc')):
    """Match exact WINEPREFIX for this user; never match process names globally."""
    wanted=b'WINEPREFIX='+os.fsencode(str(bottle))
    found=[]
    for entry in proc_root.glob('[0-9]*'):
        try:
            if int(entry.name)==os.getpid() or entry.stat().st_uid!=os.getuid(): continue
            if wanted not in (entry/'environ').read_bytes().split(b'\0'): continue
            comm=(entry/'comm').read_text().strip().lower()
            try: executable=(entry/'exe').resolve(strict=True).name.lower()
            except OSError: executable=''
            loaders={'wine','wine64','wine-preloader','wine64-preloader','wineserver','wineserver64'}
            if comm.endswith('.exe') or comm in loaders or executable in loaders:
                found.append(int(entry.name))
        except (OSError,ValueError): continue
    return found


def stop_prefix(bottle):
    # Wine processes may start separate sessions; killing only the CLI misses them.
    for signum,seconds in ((signal.SIGTERM,2),(signal.SIGKILL,2)):
        for pid in prefix_processes(bottle):
            try:
                if pid in prefix_processes(bottle): os.kill(pid,signum)
            except ProcessLookupError: pass
        until=time.monotonic()+seconds
        while prefix_processes(bottle) and time.monotonic()<until: time.sleep(.1)
        if not prefix_processes(bottle): return
    raise RuntimeError('Quedan procesos de MythCool bloqueados. No se modificará la botella mientras sigan activos.')


def start_logged(argv,path):
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    def read_log():
        with path.open('ab') as stream:
            remaining=max(0,LIMIT-stream.tell())
            try:
                while chunk:=os.read(process.stdout.fileno(),65536):
                    if remaining:
                        stream.write(chunk[:remaining]); stream.flush()
                        remaining=max(0,remaining-len(chunk))
            except (OSError,ValueError): pass
    reader=threading.Thread(target=read_log,daemon=True); reader.start()
    return process,reader


def terminate_launcher(process):
    if process is None: return
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=2)


@contextlib.contextmanager
def trial_lock(base):
    with (base/'.llano-mythcool-trial.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Ya hay otra prueba activa. Cancélala antes de continuar.')
        yield


def find_older_trial():
    script=str(Path(__file__).resolve())
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            if int(entry.name)==os.getpid() or entry.stat().st_uid!=os.getuid(): continue
            args=[os.fsdecode(a) for a in (entry/'cmdline').read_bytes().split(b'\0') if a]
            for arg in args[1:]:
                if Path(arg).name!=Path(script).name: continue
                path=Path(arg) if Path(arg).is_absolute() else (entry/'cwd').resolve()/arg
                if str(path.resolve())==script:
                    raise RuntimeError('Sigue abierto otro test-mythcool-soda.py. Cancélalo con Ctrl+C antes de reanudar.')
        except (OSError,ValueError): continue


def validate_resume(folder,bottle):
    folder=folder.expanduser().resolve()
    state=json.loads((folder/'session.json').read_text())
    backup=folder/'bottle-backup'
    if state.get('backup_complete',True) is not True:
        raise ValueError('La copia anterior quedó incompleta; no se puede reanudar desde ella.')
    if Path(state['backup']).resolve()!=backup.resolve() or not (backup/'drive_c').is_dir():
        raise ValueError('La carpeta no contiene la copia de seguridad completa de esta prueba.')
    if load_config(backup/'bottle.yml').get('Name')!='MythCool':
        raise ValueError('La copia no corresponde a MythCool.')
    if load_config(bottle/'bottle.yml').get('Runner')!=RUNNER:
        raise ValueError('La botella no está en Soda. No se reanudará una migración distinta.')
    return folder,backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',type=Path,help='Carpeta de la primera prueba con bottle-backup')
    parser.add_argument('--diagnose-launch',action='store_true',help='Registrar excepciones y módulos, sin repetir wineboot ni migración')
    args=parser.parse_args()
    if args.diagnose_launch and not args.resume: parser.error('--diagnose-launch requiere --resume')
    base=Path.home()/'.var/app'/APP/'data/bottles'
    bottle=base/'bottles/MythCool'; config_path=bottle/'bottle.yml'
    runner=base/'runners'/RUNNER
    if not runner.is_dir(): raise RuntimeError('No está instalado '+RUNNER)
    devices=[h for h in inventory()['hid'] if h['candidate']]
    if len(devices)!=1 or not os.access(devices[0]['node'],os.R_OK|os.W_OK):
        raise RuntimeError('Conecta un único Llano y comprueba sus permisos antes de esta prueba.')
    find_older_trial()
    with trial_lock(base):
        return run_trial(args,base,bottle,config_path,runner,devices)


def run_trial(args,base,bottle,config_path,runner,devices):
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    original=load_config(config_path)
    if args.resume:
        session,backup=validate_resume(args.resume,bottle)
        output=session/('resume-'+stamp)
    else:
        if original.get('Runner')==RUNNER:
            raise RuntimeError('La botella ya usa Soda. Usa --resume con la copia original; no repitas la migración.')
        output=Path.home()/('mythcool-soda-'+stamp)
        backup=output/'bottle-backup'
    output.mkdir(mode=0o700,exist_ok=False)
    state={'previous_runner':original.get('Runner'),'runner':RUNNER,'device':devices[0],
           'diagnose_launch':getattr(args,'diagnose_launch',False),
           'backup':str(backup),'backup_complete':bool(args.resume),'status':'preparing','phase':'close_previous_processes'}
    state_path=output/'session.json'
    def save_state(): state_path.write_text(json.dumps(state,indent=2))
    save_state()
    print('Cierra las ventanas de MythCool y Bottles. Se cerrarán solo los procesos de la botella MythCool.')
    input('Pulsa Intro cuando estén cerradas: ')
    process=None; reader=None; original_env=None; success=False
    try:
        stop_prefix(bottle)
        if not args.resume:
            state['phase']='backup'; save_state()
            print('Guardando copia completa antes del cambio...',flush=True)
            subprocess.run(['cp','-a','--reflink=auto',str(bottle),str(backup)],check=True)
            state['backup_complete']=True
            state['phase']='runner_change'; save_state()
            cli=['flatpak','run','--command=bottles-cli',APP]
            process,reader=start_logged(cli+['edit','-b','MythCool','--runner',RUNNER],output/'setup.log')
            process.wait(timeout=60)
            if process.returncode: raise RuntimeError('Bottles no completó el cambio de controlador.')
            stop_prefix(bottle); terminate_launcher(process); reader.join(timeout=3)
            process=None; reader=None
        if load_config(config_path).get('Runner')!=RUNNER:
            raise RuntimeError('La botella no confirmó Soda. Revisa setup.log.')
        # The previous CLI timed out after selecting Soda. Resume using its wineboot
        # directly, with the actual session display, and retain full stderr.
        if not getattr(args,'diagnose_launch',False):
            state['phase']='wineboot'; save_state()
            command=['flatpak','run','--env=WINEPREFIX='+str(bottle),
                     '--env=WINEDEBUG=-all,+timestamp,+pid,+seh,+loaddll,+process',
                     '--command='+str(runner/'bin/wine'),APP,'wineboot','-u']
            print('Comprobando la actualización de Wine (máximo 60 segundos)...',flush=True)
            process,reader=start_logged(command,output/'wineboot.log')
            process.wait(timeout=60)
            if process.returncode: raise RuntimeError('Wineboot falló. Se conserva el registro; no se abrirá MythCool.')
            stop_prefix(bottle); terminate_launcher(process); reader.join(timeout=3)
            process=None; reader=None
        config=load_config(config_path)
        original_env=dict(config.get('Environment_Variables') or {})
        enable_hid(config)
        debug=DEBUG+',+seh,+loaddll,+process' if getattr(args,'diagnose_launch',False) else DEBUG
        config.setdefault('Environment_Variables',{})['WINEDEBUG']=debug
        save_config(config_path,config)
        exe=bottle/'drive_c/Program Files (x86)/Myth.Cool/MythCool.exe'
        if not exe.is_file(): raise RuntimeError('No se encuentra MythCool.exe')
        state['phase']='mythcool_launch'; save_state()
        cli=['flatpak','run','--command=bottles-cli',APP]
        process,reader=start_logged(cli+['run','-b','MythCool','-e',str(exe),'/main'],output/'wine-hid.log')
        print('Observa si MythCool detecta el Llano. La prueba termina en 45 segundos.',flush=True)
        for _ in range(45):
            time.sleep(1)
            if process.poll() not in (None,0): raise RuntimeError('El lanzador de MythCool devolvió un error.')
        success=True; state['status']='launch_test_finished'
    except BaseException as error:
        state['status']='interrupted' if isinstance(error,(KeyboardInterrupt,EOFError)) else 'failed'
        state['error']=str(error)
        raise
    finally:
        # This finally also covers backup/migration timeouts, unlike the old helper.
        cleanup_errors=[]
        try: terminate_launcher(process)
        except Exception as error: cleanup_errors.append(str(error))
        try: stop_prefix(bottle)
        except Exception as error: cleanup_errors.append(str(error))
        if reader: reader.join(timeout=3)
        if original_env is not None:
            try:
                config=load_config(config_path); restore_debug(config,original_env); save_config(config_path,config)
            except Exception as error: cleanup_errors.append(str(error))
        state['cleanup_errors']=cleanup_errors
        if cleanup_errors: state['status']='cleanup_incomplete'
        state['finished_epoch']=time.time(); save_state()
        print('Registros: '+str(output),flush=True)
        print('Copia original conservada: '+str(backup),flush=True)
        if cleanup_errors: print('La limpieza no se completó: '+ '; '.join(cleanup_errors),file=sys.stderr)
    if success:
        print('Soda y la selección HID quedan configurados; el registro detallado se ha restaurado.')
        print('Indica al agente esta carpeta y si apareció el Llano. Los registros aún no validan comandos USB.')
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr); sys.exit(1)
    except (KeyboardInterrupt,EOFError): sys.exit(130)
