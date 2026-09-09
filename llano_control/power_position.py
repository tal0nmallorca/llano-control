"""Remember the last confirmed position without applying power at startup."""
import json
import os
from pathlib import Path
import tempfile
from .i18n import settings_path

def path():return settings_path().with_name('power-position.json')

def load_position():
    try:
        value=json.loads(path().read_text())['power']
        return value if type(value) is bool else None
    except (OSError,ValueError,KeyError,TypeError):return None

def save_position(value):
    if type(value) is not bool:raise ValueError('Invalid power position')
    dest=path();dest.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=dest.parent,delete=False) as f:
            temporary=f.name;json.dump({'power':value},f);f.flush();os.fsync(f.fileno())
        os.replace(temporary,dest)
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)
