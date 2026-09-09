#!/usr/bin/python3
"""Install locally without sudo or enabling autostart."""
from pathlib import Path
import os
import shutil
import shlex
import subprocess
import sys

source = Path(__file__).resolve().parent
base = Path.home()
destination = base / '.local/share/llano-control'
launcher = base / '.local/bin/llano-control'
desktop = base / '.local/share/applications/io.github.llanocontrol.App.desktop'
try:
    import gi
    gi.require_version('Gtk', '4.0')
    import cairo
    from gi.repository import Gtk
except (ImportError, ValueError):
    sys.exit('Faltan dependencias. Ejecuta: sudo apt install python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-4.0')
if launcher.is_symlink():
    sys.exit(f'El lanzador {launcher} es un enlace; revísalo antes de actualizar.')
if launcher.exists() and str(destination/'llano-control') not in launcher.read_text():
    sys.exit(f'El lanzador existente no pertenece a esta instalación: {launcher}')
if desktop.exists() and str(destination/'llano-control') not in desktop.read_text():
    sys.exit(f'El acceso existente no pertenece a esta instalación: {desktop}')
destination.mkdir(parents=True, exist_ok=True)
for name in ('llano_control', 'docs', 'packaging'):
    shutil.copytree(source/name, destination/name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for name in ('llano-control', 'README.md', 'README.en.md', 'README.es.md', 'LICENSE', 'NOTICE.md'):
    shutil.copy2(source/name, destination/name)
executable = destination/'llano-control'
executable.chmod(0o755)
launcher.parent.mkdir(parents=True, exist_ok=True)
launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(executable))+' "$@"\n')
launcher.chmod(0o755)
escaped = str(executable).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
desktop.parent.mkdir(parents=True, exist_ok=True)
desktop.write_text('[Desktop Entry]\nType=Application\nName=Llano Control\nComment=Perfiles y diagnóstico del Llano V12 Ultra\nExec="'+escaped+'" gui\nIcon=preferences-system\nTerminal=false\nCategories=Utility;Settings;\nStartupNotify=true\n')
subprocess.run([str(executable), 'probe'], check=True, stdout=subprocess.DEVNULL)
print('Instalado. Busca Llano Control en el menú de aplicaciones.')
print('RGB y modos del ventilador disponibles bajo demanda. RPM estimadas; validación física Linux pendiente.')
