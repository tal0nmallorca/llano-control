import unittest
from concurrent.futures import Future, TimeoutError
from types import SimpleNamespace
from unittest.mock import Mock, patch
from gi.repository import GLib
from llano_control.session_end import SessionEnd, power_off, BUS
from llano_control.gui import App


class SessionEndTests(unittest.TestCase):
    def event(self, monitor, active, kind=None):
        metadata={} if kind is None else {'type':GLib.Variant('s',kind)}
        monitor.on_shutdown(None,None,None,None,None,
            GLib.Variant('(ba{sv})',(active,metadata)))

    def test_reboot_halt_unknown_and_cancel_do_not_stop_cooling(self):
        callback=Mock(); monitor=SessionEnd(callback)
        with patch.object(monitor,'release_delay') as release:
            for kind in ('reboot','soft-reboot','kexec','halt',None,'unknown'):
                self.event(monitor,True,kind)
            self.assertEqual(release.call_count,6)
        self.event(monitor,False,'power-off')
        callback.assert_not_called()

    def test_poweroff_only_cleanup_once(self):
        callback=Mock(); monitor=SessionEnd(callback)
        self.event(monitor,True,'poweroff')
        self.event(monitor,True,'poweroff')
        callback.assert_called_once()

    def test_documented_power_off_spelling_remains_supported(self):
        callback=Mock(); monitor=SessionEnd(callback)
        self.event(monitor,True,'power-off')
        callback.assert_called_once()

    def test_start_subscribes_only_to_metadata_not_logout_or_signals(self):
        monitor=SessionEnd(Mock());bus=Mock()
        bus.call_sync.return_value.unpack.return_value=['PrepareForShutdownWithMetadata']
        with patch('llano_control.session_end.Gio.bus_get_sync',return_value=bus),patch.object(monitor,'acquire_delay'):
            monitor.start()
        bus.signal_subscribe.assert_called_once()
        self.assertEqual(bus.signal_subscribe.call_args.args[2],'PrepareForShutdownWithMetadata')

    def test_legacy_logind_selects_systemd_jobs_without_delay_lock(self):
        monitor=SessionEnd(Mock());bus=Mock()
        bus.call_sync.return_value.unpack.return_value=['<node/>']
        with patch('llano_control.session_end.Gio.bus_get_sync',return_value=bus),patch.object(monitor,'acquire_delay') as delay:
            monitor.start()
        delay.assert_not_called()
        self.assertTrue(monitor.systemd_subscribed)
        self.assertEqual(bus.signal_subscribe.call_args.args[2],'JobNew')
        monitor.close()
        self.assertFalse(monitor.systemd_subscribed)

    def test_job_fallback_ignores_reboot_shutdown_and_stop_jobs(self):
        callback=Mock(); monitor=SessionEnd(callback);monitor.bus=Mock()
        for unit in ('shutdown.target','reboot.target','halt.target','exit.target'):
            monitor.on_job(None,None,None,None,None,GLib.Variant('(uos)',(1,'/job/1',unit)))
        monitor.bus.call_sync.assert_not_called()
        monitor.bus.call_sync.return_value=GLib.Variant('(v)',(GLib.Variant('s','stop'),))
        monitor.on_job(None,None,None,None,None,GLib.Variant('(uos)',(1,'/job/1','poweroff.target')))
        callback.assert_not_called()
        monitor.bus.call_sync.return_value=GLib.Variant('(v)',(GLib.Variant('s','start'),))
        monitor.on_job(None,None,None,None,None,GLib.Variant('(uos)',(1,'/job/1','poweroff.target')))
        callback.assert_called_once()

    def test_missing_job_is_not_assumed_to_be_poweroff(self):
        callback=Mock();monitor=SessionEnd(callback);monitor.bus=Mock()
        monitor.bus.call_sync.side_effect=GLib.Error('Job vanished')
        with patch('sys.stderr'):
            monitor.on_job(None,None,None,None,None,GLib.Variant('(uos)',(1,'/job/1','poweroff.target')))
        callback.assert_not_called()

    def test_cli_off_uses_verified_helper_without_loading_gui(self):
        from llano_control.__main__ import main
        with patch('sys.argv',['llano-control','power-off']),patch('llano_control.session_end.power_off') as off:
            self.assertEqual(main(),0)
        off.assert_called_once()

    def test_off_retries_contention_but_not_missing_device(self):
        busy=SimpleNamespace(returncode=1,stderr='Resource temporarily unavailable')
        ok=SimpleNamespace(returncode=0)
        with patch('llano_control.session_end.subprocess.run',side_effect=[busy,ok]) as run, patch('llano_control.session_end.time.sleep'):
            power_off()
        self.assertEqual(run.call_count,2)
        self.assertIn('"enabled":false',run.call_args.args[0][-1])
        with patch('llano_control.session_end.subprocess.run',return_value=SimpleNamespace(returncode=1,stderr='No device')) as run:
            with self.assertRaisesRegex(OSError,'No device'):power_off()
        run.assert_called_once()

    def app(self,ending):
        executor=Mock(); future=Future();future.set_result(None)
        executor.submit.return_value=future
        return SimpleNamespace(session_ending=ending,executor=executor,
            session_end=Mock(),fan_controller=SimpleNamespace(active=True))

    def test_cleanup_drains_jobs_then_powers_off_and_releases_inhibitor(self):
        app=self.app(True);order=[]
        app.executor.submit.side_effect=lambda fn:(order.append('drain') or Future())
        ready=Future();ready.set_result(None)
        app.executor.submit.side_effect=lambda fn:(order.append('drain') or ready)
        app.session_end.close.side_effect=lambda:order.append('release')
        with patch.object(App,'persist_current') as persist,patch('llano_control.gui.power_off',side_effect=lambda **kw:order.append('off')):
            App.cleanup_tray(app)
        self.assertEqual(order,['drain','off','release'])
        persist.assert_called_once();self.assertFalse(app.fan_controller.active)

    def test_regular_quit_does_not_power_off(self):
        app=self.app(False)
        with patch.object(App,'persist_current'),patch('llano_control.gui.power_off') as off:
            App.cleanup_tray(app)
        off.assert_not_called();app.session_end.close.assert_called_once()

    def test_failure_releases_inhibitor(self):
        app=self.app(True)
        with patch.object(App,'persist_current'),patch('llano_control.gui.power_off',side_effect=OSError('Disconnected')),patch('sys.stderr'):
            App.cleanup_tray(app)
        app.session_end.close.assert_called_once()

if __name__=='__main__':unittest.main()
