#!/usr/bin/env python3
"""Export complete packet bytes and USB fields without replaying any traffic."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session',type=Path)
    args=parser.parse_args()
    metadata=json.loads((args.session/'session.json').read_text())
    device=metadata['device']; bus=int(device['bus']); address=int(device['address'])
    output=args.session/'packets.json'
    with output.open('x') as stream:
        subprocess.run(['tshark','-n','-r',str(args.session/'device.pcapng'),
                        '-Y',f'usb.bus_id == {bus} && usb.device_address == {address}',
                        '-T','json','-x'],stdout=stream,check=True)
    print(output)
    print('Incluye bytes completos, endpoints y transferencias. No se deduce ni se reproduce ningún comando.')

if __name__=='__main__': main()
