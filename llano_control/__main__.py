import argparse
import json
import os
from pathlib import Path
import select
import sys
import time
from .devices import inventory, difference

def capture(node, seconds):
    import stat
    records = inventory()["hid"]
    match = next((r for r in records if r["node"] == node and r["candidate"]), None)
    if not match: raise ValueError("Solo se permite leer un hidraw candidato 374a:b101 enumerado")
    fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISCHR(os.fstat(fd).st_mode): raise ValueError("No es dispositivo de caracteres")
        # Revalidate sysfs after opening to detect ordinary unplug/replug races.
        if match not in inventory()["hid"]: raise ValueError("La identidad cambió durante la apertura")
        print(json.dumps({"metadata": match, "mode": "passive-input-only"}), flush=True)
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            if select.select([fd], [], [], min(0.25, max(0,end-time.monotonic())))[0]:
                try: data = os.read(fd, 4096)
                except BlockingIOError: continue
                if not data: break
                print(json.dumps({"time_ns": time.time_ns(), "hex": data.hex()}), flush=True)
    finally: os.close(fd)

def main():
    parser = argparse.ArgumentParser(description="Llano Control: RGB, interfaz y diagnóstico")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("gui")
    sub.add_parser("probe")
    sub.add_parser("telemetry")
    diff = sub.add_parser("diff"); diff.add_argument("before"); diff.add_argument("after")
    cap = sub.add_parser("capture"); cap.add_argument("node"); cap.add_argument("--seconds", type=int, default=30)
    a = parser.parse_args()
    try:
        if a.cmd == "probe": print(json.dumps(inventory(), indent=2, ensure_ascii=False))
        elif a.cmd == "telemetry":
            from .telemetry import Monitor
            monitor=Monitor(); monitor.sample(); time.sleep(1)
            print(json.dumps(monitor.sample(), indent=2, ensure_ascii=False))
        elif a.cmd == "diff": print(json.dumps(difference(json.loads(Path(a.before).read_text()), json.loads(Path(a.after).read_text())), indent=2))
        elif a.cmd == "capture":
            if not 1 <= a.seconds <= 300: raise ValueError("Duración permitida: 1–300 segundos")
            capture(a.node, a.seconds)
        else:
            from .gui import run
            return run()
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__": sys.exit(main())
