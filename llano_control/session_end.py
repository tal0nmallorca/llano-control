"""Event-driven power-off only; no sensor polling or extra resident process."""
import os
import subprocess
import sys
import time
from gi.repository import Gio, GLib

BUS = 'org.freedesktop.login1'
ROOT = '/org/freedesktop/login1'
MANAGER = BUS + '.Manager'
SYSTEMD = 'org.freedesktop.systemd1'
SYSTEMD_ROOT = '/org/freedesktop/systemd1'


def power_off(timeout=3):
    """Bounded child process, using only the already verified power command.

    Retry a busy RGB/fan lock; never save the temporary off state as a profile.
    """
    end = time.monotonic() + timeout
    error = 'Shutdown USB timeout'
    while time.monotonic() < end:
        result = subprocess.run(
            [sys.executable, '-m', 'llano_control.fan',
             '{"operation":"power","enabled":false}'],
            capture_output=True, text=True, timeout=max(.01, end-time.monotonic()))
        if result.returncode == 0:
            return
        error = result.stderr.strip() or 'Shutdown USB error'
        if 'Resource temporarily unavailable' not in error:
            break
        time.sleep(.05)
    raise OSError(error)


class SessionEnd:
    """Only a positively identified power-off may stop the cooler."""
    def __init__(self, callback):
        self.callback = callback
        self.ending = False
        self.fd = None
        self.bus = None
        self.subscriptions = []
        self.systemd_subscribed = False

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error as error:
            print('Llano power-off monitor: ' + str(error), file=sys.stderr)
            return
        try:
            xml = self.bus.call_sync(BUS, ROOT,
                'org.freedesktop.DBus.Introspectable', 'Introspect', None,
                GLib.VariantType.new('(s)'), Gio.DBusCallFlags.NONE,
                1000, None).unpack()[0]
            if 'PrepareForShutdownWithMetadata' in xml:
                self.subscriptions.append(self.bus.signal_subscribe(
                    BUS, MANAGER, 'PrepareForShutdownWithMetadata', ROOT, None,
                    Gio.DBusSignalFlags.NONE, self.on_shutdown))
                self.acquire_delay()
                return
        except GLib.Error:
            pass
        # Older logind cannot distinguish reboot from power-off. Watch only a
        # confirmed start job for poweroff.target, never generic shutdown.target.
        # This arrives later, so delivery before session teardown is best effort.
        try:
            self.subscriptions.append(self.bus.signal_subscribe(
                SYSTEMD, SYSTEMD + '.Manager', 'JobNew', SYSTEMD_ROOT, None,
                Gio.DBusSignalFlags.NONE, self.on_job))
            self.bus.call_sync(SYSTEMD, SYSTEMD_ROOT, SYSTEMD + '.Manager',
                'Subscribe', None, None, Gio.DBusCallFlags.NONE, 1000, None)
            self.systemd_subscribed = True
        except GLib.Error as error:
            print('Llano: automatic power-off unavailable; use the power-off CLI hook. '
                  + str(error), file=sys.stderr)

    def end(self):
        if not self.ending:
            self.ending = True
            self.callback()

    def on_job(self, connection, sender, path, interface, signal_name, args):
        job_id, job_path, unit = args.unpack()
        if unit != 'poweroff.target' or self.ending:
            return
        try:
            job_type = self.bus.call_sync(SYSTEMD, job_path,
                'org.freedesktop.DBus.Properties', 'Get',
                GLib.Variant('(ss)', (SYSTEMD + '.Job', 'JobType')),
                GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE,
                500, None).unpack()[0]
            if job_type == 'start':
                self.end()
        except GLib.Error as error:
            print('Llano: could not verify poweroff job: ' + str(error), file=sys.stderr)

    def acquire_delay(self):
        if self.fd is not None or self.bus is None:
            return
        try:
            reply, fds = self.bus.call_with_unix_fd_list_sync(
                BUS, ROOT, MANAGER, 'Inhibit',
                GLib.Variant('(ssss)', ('shutdown', 'Llano Control',
                    'Power off the cooler', 'delay')),
                GLib.VariantType.new('(h)'), Gio.DBusCallFlags.NONE,
                1000, None, None)
            self.fd = fds.get(reply.unpack()[0])
        except GLib.Error as error:
            print('Llano shutdown delay: ' + str(error), file=sys.stderr)

    def release_delay(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def on_shutdown(self, connection, sender, path, interface, signal_name, args):
        active, metadata = args.unpack()
        if not active:
            self.acquire_delay()  # e.g. a cancelled reboot
        # systemd's handle_action_table emits poweroff; some manuals say power-off.
        elif metadata.get('type') in ('poweroff', 'power-off'):
            self.end()
        else:
            # Reboot/halt/unknown: no USB write and no unnecessary delay.
            self.release_delay()

    def close(self):
        if self.bus and self.systemd_subscribed:
            try:
                self.bus.call_sync(SYSTEMD, SYSTEMD_ROOT, SYSTEMD + '.Manager',
                    'Unsubscribe', None, None, Gio.DBusCallFlags.NONE, 500, None)
            except GLib.Error:
                pass
            self.systemd_subscribed = False
        if self.bus:
            for subscription in self.subscriptions:
                self.bus.signal_unsubscribe(subscription)
        self.subscriptions.clear()
        self.release_delay()
