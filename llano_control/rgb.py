"""RGB Feature reports derived from labeled Windows captures, September 2026.

No background writes. Each operation reads state, changes only RGB, then verifies.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import time
from .core import EFFECTS
from .devices import inventory

COLORS = {'#ff3355': 0, '#3985ff': 1, '#38dc8c': 2, '#aa55ff': 3, '#ffcf40': 4}
DESCRIPTOR_HASH = '298c8c11a3b2ab29539a64e94d5fc893cdf299e27193c681734bade8cd7ea136'
QUERY = bytes.fromhex('80 00 00 00 00 00 00 7f')


def checked_state(data):
    if len(data) != 8 or sum(data) & 255 != 255 or data[0] not in (0x80, 0x88):
        raise ValueError('Respuesta HID inválida / Invalid HID response')
    if data[1] > 100 or data[2] not in (0, 1) or data[3] & 0x7f > 3 or data[4] > 4 or data[5] > 3:
        raise ValueError('Estado HID desconocido / Unknown HID state')
    return data


def rgb_report(state, settings):
    checked_state(state)
    if type(settings['rgb']) is not bool or settings['effect'] not in EFFECTS or settings['color'] not in COLORS:
        raise ValueError('Ajuste RGB no compatible / Unsupported RGB setting')
    for key, maximum in (('brightness',255), ('animation_speed',3)):
        if type(settings[key]) is not int or not 0 <= settings[key] <= maximum:
            raise ValueError('Valor RGB fuera de rango / RGB value out of range')
    # Never echo the response flags (80/88) or use the PC takeover command (01).
    body = bytes([0, state[1], state[2], EFFECTS.index(settings['effect']) | (0 if settings['rgb'] else 128),
                  COLORS[settings['color']], 3-settings['animation_speed'], settings['brightness']])
    return body + bytes([(255-sum(body)) & 255])


def ioctl_code(direction, number, length):
    return direction << 30 | length << 16 | ord('H') << 8 | number


class HidFeature:
    def __enter__(self):
        candidates = [d for d in inventory()['hid'] if d['candidate'] and d.get('descriptor_sha256') == DESCRIPTOR_HASH]
        if len(candidates) != 1:
            raise OSError('Conecta un único Llano compatible / Connect one compatible Llano')
        self.fd = os.open(candidates[0]['node'], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            info=bytearray(8); fcntl.ioctl(self.fd, ioctl_code(2,3,8), info)
            if struct.unpack('=IHH', info) != (3, 0x374a, 0xb101):
                raise OSError('Identidad HID distinta / HID identity changed')
            size=bytearray(4); fcntl.ioctl(self.fd, ioctl_code(2,1,4), size)
            count=struct.unpack('=I',size)[0]
            if not 1 <= count <= 4096: raise OSError('Invalid HID descriptor length')
            descriptor=bytearray(struct.pack('=I',count)+bytes(4096))
            fcntl.ioctl(self.fd,ioctl_code(2,2,4100),descriptor)
            if hashlib.sha256(descriptor[4:4+count]).hexdigest()!=DESCRIPTOR_HASH:
                raise OSError('Descriptor HID distinto / HID descriptor changed')
        except BaseException:
            os.close(self.fd); raise
        return self

    def __exit__(self,*_): os.close(self.fd)

    def send(self, report):
        buf=bytearray(b'\0'+report)
        if fcntl.ioctl(self.fd,ioctl_code(3,6,9),buf)!=9:
            raise OSError('Envío HID incompleto / Short HID send')

    def state(self):
        self.send(QUERY); time.sleep(.012)
        buf=bytearray(9)
        size=fcntl.ioctl(self.fd,ioctl_code(3,7,9),buf)
        # Linux USB unnumbered reports normally return eight payload bytes.
        if size==8: data=bytes(buf[:8])
        elif size==9 and buf[0]==0: data=bytes(buf[1:])
        else: raise OSError('Lectura HID incompleta / Short HID read')
        return checked_state(data)


def apply_rgb(settings, transport=HidFeature):
    with transport() as device:
        before=device.state()
        report=rgb_report(before,settings)
        if before[3:7]==report[3:7]: return {'changed':False}
        device.send(report)
        time.sleep(.05)
        after=device.state()
        if after[3:7]!=report[3:7]:
            raise OSError('RGB no confirmado por el dispositivo / RGB not confirmed by device')
        if before[:3]!=after[:3]:
            raise OSError('El estado del ventilador cambió durante la operación / Fan state changed during operation')
        return {'changed':True}


def main():
    import sys
    try:
        settings=json.loads(sys.argv[1])
        runtime=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))
        with (runtime/'llano-control-rgb.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            result=apply_rgb(settings)
        print(json.dumps(result))
    except Exception as error:
        print(str(error),file=sys.stderr); sys.exit(1)

if __name__=='__main__': main()
