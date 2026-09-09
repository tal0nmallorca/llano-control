#!/usr/bin/env python3
"""Check host and Flatpak access to the verified Llano HID, without opening it."""
import datetime
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llano_control.devices import inventory


def main():
    result={'time':datetime.datetime.now().isoformat(),'uid':os.getuid(),'checks':[]}
    candidates=[d for d in inventory()['hid'] if d['candidate']]
    for device in candidates:
        path=Path(device['node'])
        item={'node':str(path),'identity':device['hid_id'],'host_read':os.access(path,os.R_OK),
              'host_write':os.access(path,os.W_OK)}
        try:
            info=path.stat()
            item.update(owner_uid=info.st_uid,owner_gid=info.st_gid,permissions=stat.filemode(info.st_mode))
        except OSError as error: item['host_error']=str(error)
        try:
            acl=subprocess.run(['getfacl','-p',str(path)],capture_output=True,text=True,timeout=5)
            item['acl']=acl.stdout or acl.stderr
        except (OSError,subprocess.TimeoutExpired) as error: item['acl_error']=str(error)
        # The same Flatpak app permissions as Bottles, with positional path argument.
        try:
            check=subprocess.run(['flatpak','run','--command=sh','com.usebottles.bottles','-c',
                                  'test -e "$1" && echo EXISTS; test -r "$1" && echo READ; test -w "$1" && echo WRITE; exit 0',
                                  'llano-check',str(path)],capture_output=True,text=True,timeout=30)
            item['flatpak_exit']=check.returncode
            item['flatpak_access']=check.stdout.splitlines()
            item['flatpak_error']=check.stderr
        except (OSError,subprocess.TimeoutExpired) as error: item['flatpak_error']=str(error)
        result['checks'].append(item)
    output=Path.cwd()/('mythcool-usb-check-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False))
    if not candidates: print('El Llano no aparece en el inventario HID.')
    for item in result['checks']:
        print(item['node'], 'lectura:',item['host_read'],'escritura:',item['host_write'])
        print('Acceso dentro de Bottles:',', '.join(item.get('flatpak_access',[])) or 'no confirmado')
        if not item['host_read'] or not item['host_write']:
            print('Primero hay que corregir permisos del dispositivo en Linux.')
        elif {'EXISTS','READ','WRITE'}<=set(item.get('flatpak_access',[])):
            print('Permisos básicos correctos: siguiente paso, revisar Soda/HIDRAW y los registros Wine.')
        else: print('Hay que revisar el acceso de Flatpak antes de cambiar el controlador.')
    print('Resultado: '+str(output.resolve()))
    return 0

if __name__=='__main__': sys.exit(main())
