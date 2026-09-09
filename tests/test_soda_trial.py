import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('soda_trial',Path(__file__).resolve().parents[1]/'tools/test-mythcool-soda.py')
trial=importlib.util.module_from_spec(spec); spec.loader.exec_module(trial)

class SodaTrialTests(unittest.TestCase):
    def test_hid_selection_preserves_other_devices_and_settings(self):
        config={'Runner':'soda-11.0-9','Parameters':{'hidraw_devices':['0x1234/0x5678'],'dxvk':False},'External_Programs':{'entry':'unchanged'}}
        trial.enable_hid(config); trial.enable_hid(config)
        self.assertEqual(config['Parameters']['hidraw_devices'],['0x1234/0x5678','0x374A/0xB101'])
        self.assertFalse(config['Parameters']['dxvk'])
        self.assertEqual(config['External_Programs'],{'entry':'unchanged'})
    def test_debug_restore_preserves_exact_original_and_other_variables(self):
        for original in ({},{'WINEDEBUG':'+warn'}):
            config={'Environment_Variables':{'WINEDEBUG':trial.DEBUG,'OTHER':'keep'}}
            trial.restore_debug(config,original)
            self.assertEqual(config['Environment_Variables'],{'OTHER':'keep',**original})
    def test_atomic_config_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bottle.yml'
            config={'Name':'MythCool','Parameters':{'hidraw_devices':[]},'Environment_Variables':{}}
            trial.save_config(path,config)
            self.assertEqual(trial.load_config(path),config)
            self.assertEqual(list(Path(d).iterdir()),[path])
    def test_invalid_device_configuration_is_not_overwritten(self):
        config={'Parameters':{'hidraw_devices':'bad value'}}
        with self.assertRaises(ValueError): trial.enable_hid(config)
        self.assertEqual(config['Parameters']['hidraw_devices'],'bad value')

class RecoveryTests(unittest.TestCase):
    def test_lock_excludes_parallel_trials(self):
        with tempfile.TemporaryDirectory() as d:
            with trial.trial_lock(Path(d)):
                with self.assertRaises(RuntimeError):
                    with trial.trial_lock(Path(d)): pass
            with trial.trial_lock(Path(d)): pass

    def test_prefix_selection_is_exact(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for pid,prefix in [(11111,'/bottles/MythCool'),(22222,'/bottles/MythCool-other'),(33333,'/bottles/Game')]:
                process=root/str(pid); process.mkdir()
                (process/'environ').write_bytes(b'OTHER=test\0WINEPREFIX='+prefix.encode()+b'\0')
                (process/'comm').write_text('wineserver')
            shell=root/'44444'; shell.mkdir()
            (shell/'environ').write_bytes(b'WINEPREFIX=/bottles/MythCool\0')
            (shell/'comm').write_text('bash')
            self.assertEqual(trial.prefix_processes(Path('/bottles/MythCool'),root),[11111])

    def test_resume_timeout_cleans_up_and_retains_backup(self):
        import argparse, contextlib, io, json, subprocess
        from unittest.mock import Mock,patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); bottle=root/'MythCool'; bottle.mkdir()
            config={'Name':'MythCool','Runner':trial.RUNNER,'Parameters':{},'Environment_Variables':{'OTHER':'keep'}}
            trial.save_config(bottle/'bottle.yml',config)
            session=root/'original-session'; backup=session/'bottle-backup'; (backup/'drive_c').mkdir(parents=True)
            trial.save_config(backup/'bottle.yml',{'Name':'MythCool','Runner':'caffe-10.0'})
            (session/'session.json').write_text(json.dumps({'backup':str(backup)}))
            process=Mock(); process.wait.side_effect=subprocess.TimeoutExpired('wineboot',60)
            reader=Mock()
            with patch('builtins.input',return_value=''),patch.object(trial,'stop_prefix') as stop,patch.object(trial,'terminate_launcher') as terminate,patch.object(trial,'start_logged',return_value=(process,reader)),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.TimeoutExpired):
                    trial.run_trial(argparse.Namespace(resume=session),root,bottle,bottle/'bottle.yml',root/'runner',[{'node':'fake'}])
            self.assertEqual(stop.call_count,2)
            terminate.assert_called_once_with(process)
            reader.join.assert_called_once()
            state=json.loads(next(session.glob('resume-*/session.json')).read_text())
            self.assertEqual(state['phase'],'wineboot')
            self.assertEqual(state['status'],'failed')
            self.assertEqual(state['cleanup_errors'],[])
            self.assertEqual(trial.load_config(bottle/'bottle.yml'),config)
            self.assertEqual(trial.load_config(backup/'bottle.yml')['Runner'],'caffe-10.0')

    def test_partial_backup_rejected(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'session.json').write_text(json.dumps({'backup_complete':False}))
            with self.assertRaises(ValueError): trial.validate_resume(root,root/'MythCool')

    def test_diagnostic_launch_skips_migration_and_restores_debug(self):
        import argparse,contextlib,io,json
        from unittest.mock import Mock,patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); bottle=root/'MythCool'; bottle.mkdir()
            config={'Name':'MythCool','Runner':trial.RUNNER,'Parameters':{},'Environment_Variables':{'WINEDEBUG':'-all'}}
            trial.save_config(bottle/'bottle.yml',config)
            exe=bottle/'drive_c/Program Files (x86)/Myth.Cool/MythCool.exe'; exe.parent.mkdir(parents=True); exe.touch()
            session=root/'original'; backup=session/'bottle-backup'; (backup/'drive_c').mkdir(parents=True)
            trial.save_config(backup/'bottle.yml',{'Name':'MythCool','Runner':'caffe-10.0'})
            (session/'session.json').write_text(json.dumps({'backup':str(backup)}))
            process=Mock(); process.poll.return_value=0; reader=Mock()
            def start(argv,path):
                debug=trial.load_config(bottle/'bottle.yml')['Environment_Variables']['WINEDEBUG']
                self.assertIn('+seh',debug); self.assertIn('+loaddll',debug)
                return process,reader
            with patch('builtins.input',return_value=''),patch.object(trial,'stop_prefix'),patch.object(trial,'terminate_launcher'),patch.object(trial,'start_logged',side_effect=start) as launch,patch.object(trial.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                trial.run_trial(argparse.Namespace(resume=session,diagnose_launch=True),root,bottle,bottle/'bottle.yml',root/'runner',[{'node':'fake'}])
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args[0][-1],'/main')
            self.assertNotIn('wineboot',launch.call_args.args[0])
            restored=trial.load_config(bottle/'bottle.yml')
            self.assertEqual(restored['Environment_Variables'],{'WINEDEBUG':'-all'})
            self.assertEqual(restored['Parameters']['hidraw_devices'],[trial.DEVICE])
