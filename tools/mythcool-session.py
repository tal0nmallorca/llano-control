#!/usr/bin/env python3
"""Guided local session: launch MythCool, identify USB, record separate actions."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llano_control.devices import inventory


def yes(prompt):
    return input(prompt+' [s/N]: ').strip().lower() in ('s','si','sí','y','yes')


def main():
    folder=Path.cwd()/('mythcool-session-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(mode=0o700,exist_ok=False)
    with (folder/'launch.log').open('w') as log:
        launch=subprocess.Popen(['flatpak','run','--command=bottles-cli','com.usebottles.bottles',
                                 'run','-b','MythCool','-p','MythCool','/main'],stdout=log,stderr=subprocess.STDOUT)
    print('Abriendo MythCool en Bottles. Registro: '+str(folder/'launch.log'))
    print('Mantén conectada la alimentación de la base. Vamos a identificar su cable de datos.')
    input('Desconecta SOLO el cable USB de datos del V12 y pulsa Intro: ')
    before=inventory()
    input('Conecta de nuevo el cable USB de datos del V12, espera a que se detecte y pulsa Intro: ')
    after=inventory()
    old={d['path']:(d['vid'],d['pid']) for d in before['usb']}
    added=[d for d in after['usb'] if old.get(d['path'])!=(d['vid'],d['pid']) and not d['path'].startswith('usb')]
    (folder/'identification.json').write_text(json.dumps({'before':before,'after':after,'added':added},indent=2,ensure_ascii=False))
    if len(added)!=1:
        print('Aparecieron '+str(len(added))+' dispositivos. Hay que revisar identification.json antes de capturar.'); return 1
    device=added[0]
    print(f"Dispositivo aparecido: {device['product']} · {device['vid']}:{device['pid']} · puerto {device['path']}")
    if not yes('¿Confirmas que ese cambio corresponde a la base y MythCool la muestra conectada?'):
        print('Sesión detenida sin captura ni órdenes USB. Conserva los registros para revisar la detección.'); return 1
    print('Selecciona Manual en MythCool, deja 1200 RPM y comprueba el resultado físico.')
    if not yes('¿La base responde físicamente al control de MythCool?'):
        print('Primero hay que resolver la comunicación de MythCool/Bottles. No se pueden validar órdenes con la interfaz sola.'); return 1
    capture=Path(__file__).with_name('capture-mythcool.py')
    analyze=Path(__file__).with_name('analyze-mythcool.py')
    actions=[('01-idle','Sin tocar controles; mantener 1200 RPM'),
             ('02-rpm-up','Cambiar una sola vez de 1200 a 1300 RPM'),
             ('03-rpm-down','Cambiar una sola vez de 1300 a 1200 RPM')]
    marks=[]
    for name,action in actions:
        print('\nSiguiente toma: '+action)
        input('Pulsa Intro para prepararla; haz la acción cuando aparezca «Iniciando captura»: ')
        output=folder/name
        started=time.time()
        result=subprocess.run([sys.executable,str(capture),'--device',device['path'],'--seconds','20',
                               '--action',action,'--output',str(output)])
        if result.returncode:
            print('Captura fallida; revisa los registros antes de continuar.'); return result.returncode
        metadata=json.loads((output/'session.json').read_text())
        if not metadata.get('packets'):
            print('No se observaron paquetes de este dispositivo. No seguimos acumulando tomas vacías.'); return 1
        observed=input('Resultado físico observado (indica también si no cambió): ')
        (output/'observed.txt').write_text(action+'\nResultado físico: '+observed+'\n')
        marks.append({'action':action,'prompt_epoch':started,'noted_epoch':time.time(),'observed':observed})
        (folder/'actions.json').write_text(json.dumps(marks,indent=2,ensure_ascii=False))
        subprocess.run([sys.executable,str(analyze),str(output)],check=True)
    print('\nSesión guardada: '+str(folder.resolve()))
    print('Pasa esta ruta al agente para comparar las tres tomas. Todavía no se ha implementado ni reproducido ningún comando.')
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr); sys.exit(1)
    except (KeyboardInterrupt,EOFError): sys.exit(130)
