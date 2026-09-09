import hashlib
from pathlib import Path

CANDIDATE = ("374a", "b101")

def read(path):
    try: return path.read_text().strip()
    except (OSError, UnicodeError): return ""

def inventory(base=Path("/sys")):
    usb = []
    for p in sorted((base/"bus/usb/devices").glob("*")):
        vid, pid = read(p/"idVendor"), read(p/"idProduct")
        if not vid or not pid: continue
        usb.append({"path": p.name, "vid": vid, "pid": pid,
            "manufacturer": read(p/"manufacturer"), "product": read(p/"product"),
            "bus": read(p/"busnum"), "address": read(p/"devnum"),
            "candidate": (vid.lower(), pid.lower()) == CANDIDATE})
    hid = []
    for p in sorted((base/"class/hidraw").glob("hidraw*")):
        device = (p/"device").resolve()
        props = dict(line.split("=",1) for line in read(device/"uevent").splitlines() if "=" in line)
        ident = props.get("HID_ID", "").split(":")
        candidate = len(ident)==3 and ident[0].lower()=="0003" and ident[1].lower().lstrip("0")=="374a" and ident[2].lower().lstrip("0")=="b101"
        try:
            descriptor = (device/"report_descriptor").read_bytes()
            report = {"descriptor_hex": descriptor.hex(), "descriptor_sha256": hashlib.sha256(descriptor).hexdigest()}
        except OSError as e: report = {"descriptor_error": str(e)}
        hid.append({"node": "/dev/"+p.name, "sysfs": str(device), "hid_id": props.get("HID_ID", ""),
            "name": props.get("HID_NAME", ""), "candidate": candidate, **report})
    return {"usb": usb, "hid": hid}

def sensors(base=Path("/sys/class/hwmon")):
    result = {}
    for hw in sorted(base.glob("hwmon*")):
        for p in sorted(hw.glob("temp*_input")):
            try:
                temp = float(p.read_text())/1000
                if -20 <= temp <= 150:
                    key = str(hw.resolve()/p.name)
                    result[key] = {"label": read(hw/"name")+" / "+(read(p.with_name(p.name.replace("_input","_label"))) or p.stem), "celsius": temp}
            except (OSError, ValueError): pass
    return result

def difference(before, after):
    return {kind: {"added": [d for d in after[kind] if d not in before[kind]],
        "removed": [d for d in before[kind] if d not in after[kind]]} for kind in ("usb", "hid")}
