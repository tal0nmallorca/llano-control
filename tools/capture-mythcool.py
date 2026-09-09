#!/usr/bin/env python3
"""Capture one identified USB device via usbmon; never send USB commands."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llano_control.devices import inventory


def select_device(devices, path=None):
    matches=[d for d in devices if d['path']==path] if path else [d for d in devices if d['candidate']]
    if len(matches)!=1:
        raise ValueError('Identifica primero la base: debe haber exactamente un candidato, o indicar --device PUERTO verificado.')
    device=matches[0]
    bus,address=int(device['bus']),int(device['address'])
    if not 1<=bus<=65535 or not 1<=address<=127: raise ValueError('Bus/dirección USB inválidos')
    return device,bus,address


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--device',help='Puerto sysfs verificado, por ejemplo 3-5; no un hidraw')
    parser.add_argument('--seconds',type=int,default=30)
    parser.add_argument('--action',default='baseline',help='Acción que vas a realizar en MythCool')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    snapshot=inventory()
    if args.list:
        for d in snapshot['usb']:
            print(d['path'],d['vid']+':'+d['pid'],d['product'],'[candidato]' if d['candidate'] else '')
        return 0
    if not 5<=args.seconds<=120: parser.error('--seconds: 5–120')
    try: device,bus,address=select_device(snapshot['usb'],args.device)
    except ValueError as e: parser.error(str(e))
    for name in ('sudo','modprobe','dumpcap','tshark'):
        if shutil.which(name) is None: parser.error('Falta '+name)
    print(f"Dispositivo: {device['product']} {device['vid']}:{device['pid']} · bus {bus}, dirección {address}")
    print('Se observará ese bus; solo se guardan paquetes de la dirección elegida. No reconectes el USB durante la captura.')
    print('La contraseña, si se solicita, la pide sudo en tu terminal; no la compartas.')
    subprocess.run(['sudo','-v'],check=True)
    subprocess.run(['sudo','-n','modprobe','usbmon'],check=True)
    # Recheck after the privilege prompt to catch unplug/replug/address changes.
    current,_,_=select_device(inventory()['usb'],device['path'])
    if any(current[k]!=device[k] for k in ('vid','pid','bus','address')):
        raise RuntimeError('El USB ha cambiado. Repite la identificación.')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    folder=args.output or Path.cwd()/('mythcool-capture-'+stamp)
    folder.mkdir(mode=0o700,parents=True,exist_ok=False)
    os.chmod(folder,0o700)
    metadata={'device':device,'hid':[h for h in snapshot['hid'] if '/'+device['path']+'/' in h['sysfs']],
              'seconds':args.seconds,'action':args.action,'started_epoch':time.time(),
              'status':'starting','filter':f'usb.bus_id == {bus} && usb.device_address == {address}'}
    meta=folder/'session.json'
    def save(): meta.write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    save()
    capture=None; writer=None
    try:
        with (folder/'capture.log').open('w') as log:
            capture=subprocess.Popen(['sudo','-n','dumpcap','-q','-i',f'usbmon{bus}','-s','0',
                                      '-a',f'duration:{args.seconds}','-a','filesize:32768','-w','-'],
                                     stdout=subprocess.PIPE,stderr=log)
            writer=subprocess.Popen(['tshark','-n','-r','-','-Y',metadata['filter'],'-w',str(folder/'device.pcapng')],
                                    stdin=capture.stdout,stdout=subprocess.DEVNULL,stderr=log)
            capture.stdout.close()
            print('Iniciando captura. Realiza solo esta acción en MythCool: '+args.action,flush=True)
            capture_code=capture.wait(timeout=args.seconds+15)
            writer_code=writer.wait(timeout=15)
        metadata.update(capture_exit=capture_code,filter_exit=writer_code)
        if capture_code or writer_code: raise RuntimeError('Captura fallida: revisa capture.log')
        # Do not mistake an empty capture for a validated command.
        result=subprocess.run(['tshark','-n','-r',str(folder/'device.pcapng'),'-T','fields','-e','frame.number'],capture_output=True,text=True,check=True)
        metadata['packets']=len(result.stdout.splitlines())
        metadata['status']='captured' if metadata['packets'] else 'no_device_traffic'
        print(f"Guardados {metadata['packets']} paquetes en {folder}")
        print('Anota el valor anterior, el nuevo y el resultado físico en observed.txt.')
        (folder/'observed.txt').write_text('Valor anterior:\nValor nuevo:\nResultado físico observado:\n')
    except BaseException:
        metadata['status']='failed_or_interrupted'
        raise
    finally:
        # Stop the unprivileged filter; privileged capture has bounded duration/size.
        if writer and writer.poll() is None:
            writer.terminate()
            try: writer.wait(timeout=3)
            except subprocess.TimeoutExpired: writer.kill(); writer.wait()
        metadata['finished_epoch']=time.time(); save()
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        print(str(e),file=sys.stderr); sys.exit(1)
    except KeyboardInterrupt: sys.exit(130)
