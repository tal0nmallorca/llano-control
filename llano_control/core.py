import copy
import json
import math
import os
from pathlib import Path
import tempfile

MODES = ("Manual", "Low", "Medium", "High", "Custom")
AI_CURVES = {
    "Low": ((30, 300), (90, 1000)),
    "Medium": ((30, 600), (90, 2000)),
    "High": ((30, 1000), (90, 2800)),
}

def effective_curve(profile):
    if profile['mode'] == 'Manual':
        rpm = rpm_step(profile['rpm'])
        return ((30,300),(90,rpm)) if profile.get("manual_thermal",False) else ((0, rpm), (110, rpm))
    return AI_CURVES.get(profile['mode'], profile['curve'])

EFFECTS = ("Solid Color", "Breathing Effect", "Color Gradient", "Color Chase")
DEFAULT = {"version": 1, "active": "Equilibrado", "profiles": {"Equilibrado": {
    "mode": "Manual", "rpm": 1200, "power": True, "rgb": True,
    "effect": "Solid Color", "color": "#aa55ff", "brightness": 50,
    "animation_speed": 50, "sensor": "", "hysteresis": 3,
    "curve": [[30, 600], [50, 1000], [70, 1800], [90, 2800]]}}}

def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()/".config"))) / "llano-control/profiles.json"

def number(x, low, high):
    if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or not low <= x <= high:
        raise ValueError(f"Valor fuera de rango {low}–{high}: {x}")

def validate(data):
    import re
    if data.get("version") != 1 or not isinstance(data.get("profiles"), dict) or not data["profiles"]:
        raise ValueError("Formato de perfiles no compatible")
    if data.get("active") not in data["profiles"]:
        raise ValueError("Perfil activo inexistente")
    for name, p in data["profiles"].items():
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError("Nombre de perfil inválido")
        if p["mode"] not in MODES or p["effect"] not in EFFECTS:
            raise ValueError("Modo o efecto desconocido")
        for k in ("power", "rgb"):
            if type(p[k]) is not bool: raise ValueError("Estado inválido")
        if not isinstance(p["sensor"], str): raise ValueError("Sensor inválido")
        if p.get('temperature_source','cpu') not in ('cpu','gpu','both'):raise ValueError('Fuente de temperatura inválida')
        if not isinstance(p.get('control_gpu',''),str):raise ValueError('GPU inválida')
        if type(p.get('manual_thermal',False)) is not bool:raise ValueError('Modo manual inválido')
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", p["color"]): raise ValueError("Color: usa #RRGGBB")
        number(p["rpm"], 300, 2800)
        if p.get("rgb_units") not in (None, "native"):
            raise ValueError("Unidades RGB desconocidas")
        number(p["brightness"], 0, 255 if p.get("rgb_units") == "native" else 100)
        number(p["animation_speed"], 0, 3 if p.get("rgb_units") == "native" else 100)
        number(p["hysteresis"], 0, 10)
        curve = p["curve"]
        if not isinstance(curve, list) or not 2 <= len(curve) <= 32: raise ValueError("Curva: 2–32 puntos")
        last = -1
        for t, rpm in curve:
            number(t, 0, 110); number(rpm, 300, 2800)
            if t <= last: raise ValueError("Temperaturas deben ser crecientes y únicas")
            last = t
    return data

def load(path=None):
    path = path or config_path()
    return validate(json.loads(path.read_text())) if path.exists() else copy.deepcopy(DEFAULT)

def save(data, path=None):
    validate(data)
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".profiles-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def interpolate(curve, temp):
    if temp <= curve[0][0]: return curve[0][1]
    for (t0, r0), (t1, r1) in zip(curve, curve[1:]):
        if temp <= t1: return round(r0 + (r1-r0)*(temp-t0)/(t1-t0))
    return curve[-1][1]

def rpm_step(value):
    number(value, 300, 2800)
    return min(2800, max(300, int((value + 50) // 100) * 100))

class Preview:
    def __init__(self): self.last_temp = None; self.last_rpm = None; self.last_settings = None
    def calculate(self, profile, temp):
        settings=(profile['mode'], profile['power'], profile['rpm'], profile['hysteresis'], tuple(map(tuple,effective_curve(profile))),profile.get('temperature_source','cpu'),profile.get('control_gpu',''),profile.get('sensor',''))
        if settings != self.last_settings:
            self.last_temp = None; self.last_rpm = None; self.last_settings = settings
        if not profile["power"]: return None
        if profile["mode"] == "Manual" and not profile.get("manual_thermal",False): return rpm_step(profile["rpm"])
        if temp is None or not math.isfinite(temp):
            self.last_temp = None; self.last_rpm = None
            return None
        if self.last_temp is not None and abs(temp-self.last_temp) < profile["hysteresis"]:
            return self.last_rpm
        result = rpm_step(interpolate(effective_curve(profile), temp))
        self.last_temp, self.last_rpm = temp, result
        return result
