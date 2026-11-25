"""Cloud sync service, agent bridge sync and window status against a fake Supabase.
Stores are temporary; the only real credential written is a uniquely named test entry
that is deleted again."""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

import cloud_sync
import taskflow_agent
from cloud_sync import CloudSync, MemoryCredentials
from supabase_sync import LinkCallback
from task_manager import TaskManager
from test_supabase_sync import KEY, URL, FakeSupabase

CONFIG = {'url': URL, 'key': KEY, 'email': 'demo@example.test', 'enabled': True}


class TestCloudSync(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.backend = FakeSupabase()
        self.credentials = MemoryCredentials()

    def tearDown(self):
        self.temp.cleanup()

    def store(self, name, config=CONFIG):
        manager = TaskManager(self.root / name / 'data.sqlite3')
        if config:
            manager.settings[cloud_sync.SETTING] = dict(config)
            manager.save()
        return manager

    def service(self, manager, credentials=None):
        return CloudSync(manager.db_file, credentials or self.credentials, opener=self.backend)

    def sign_in(self, manager):
        callback = LinkCallback(port=0)
        opened = threading.Thread(target=lambda: urllib.request.urlopen(callback.url + '?code=auth-code', timeout=5).read())
        self.service(manager).sign_in(CONFIG, callback, on_sent=opened.start, timeout=5)
        opened.join()

    def test_off_and_signed_out_states_do_not_touch_the_network(self):
        plain = self.store('plain', config=None)
        self.assertEqual(self.service(plain).run()['state'], 'off')
        off = self.store('off', dict(CONFIG, enabled=False))
        self.assertEqual(self.service(off).run()['state'], 'off')
        signed_out = self.store('signed-out')
        self.assertEqual(self.service(signed_out).run()['state'], 'signed_out')
        self.assertEqual(self.backend.requests, [])
        self.assertFalse(Path(signed_out.db_file + cloud_sync.BACKUP_SUFFIX).exists())

    def test_sign_in_keeps_session_outside_the_store_and_two_stores_sync(self):
        a, b = self.store('a'), self.store('b')
        self.sign_in(a)
        target = cloud_sync.credential_target(CONFIG)
        self.assertEqual(target, 'TaskFlow Supabase demo-project.supabase.co')
        self.assertEqual(json.loads(self.credentials.read(target))['refresh_token'], 'refresh-1')
        for path in self.root.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'refresh-1', path.read_bytes(), path)
        task = a.add_task('Bulut görevi', 'Demo')
        a.edit_notes(task['id'], 'A notu')
        status = self.service(a).run()
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(self.service(b).run()['state'], 'ok')
        b.load()
        self.assertEqual([(t['title'], t['notes']) for t in b.tasks], [('Bulut görevi', 'A notu')])
        self.assertEqual(b.settings[cloud_sync.SETTING], CONFIG)

    def test_first_sync_backs_up_once_and_never_replaces_the_backup(self):
        a = self.store('a')
        a.add_task('Önceki görev', 'Demo')
        self.sign_in(a)
        status = self.service(a).run()
        backup = Path(a.db_file + cloud_sync.BACKUP_SUFFIX)
        self.assertEqual(status['backup'], str(backup))
        conn = sqlite3.connect(backup)
        try:
            titles = [json.loads(row[0])['title'] for row in conn.execute('SELECT payload FROM tasks')]
        finally:
            conn.close()
        self.assertEqual(titles, ['Önceki görev'])
        first = backup.read_bytes()
        a.add_task('Sonraki görev', 'Demo')
        self.assertNotIn('backup', self.service(a).run())
        self.assertEqual(backup.read_bytes(), first)

    def test_revoked_session_signs_out_but_network_failure_keeps_it(self):
        a = self.store('a')
        self.sign_in(a)
        target = cloud_sync.credential_target(CONFIG)

        def offline(request, timeout):
            raise urllib.error.URLError('no route')
        status = CloudSync(a.db_file, self.credentials, opener=offline).run()
        self.assertEqual(status['state'], 'offline')
        self.assertIsNotNone(self.credentials.read(target))
        session = json.loads(self.credentials.read(target))
        session.update(expires_at=0, refresh_token='revoked')
        self.credentials.write(target, json.dumps(session))
        status = self.service(a).run()
        self.assertEqual(status['state'], 'signed_out')
        self.assertIn('Invalid Refresh Token', status['message'])
        self.assertIsNone(self.credentials.read(target))

    def test_one_sync_at_a_time_per_store(self):
        a = self.store('a')
        with cloud_sync.store_lock(a.db_file):
            with self.assertRaises(TimeoutError):
                with cloud_sync.store_lock(a.db_file, timeout=0.3):
                    pass
        with cloud_sync.store_lock(a.db_file, timeout=0.3):
            pass

    def bridge(self, manager, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch('cloud_sync.default_credentials', return_value=self.credentials), \
                patch('urllib.request.urlopen', self.backend), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = taskflow_agent.main(['--db', manager.db_file, *args])
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_bridge_sees_and_publishes_claims_across_computers(self):
        a, b = self.store('a'), self.store('b')
        self.sign_in(a)
        task = a.add_task('Ortak görev', 'Demo')
        self.service(a).run()
        repo_a, repo_b = self.root / 'repo-a', self.root / 'repo-b'
        for repo in (repo_a, repo_b):
            repo.mkdir()
            (repo / '.git').mkdir()
        code, listed = self.bridge(b, 'list', '--project', 'Demo')
        self.assertEqual(code, 2, listed)  # project arrives, binding is per computer
        TaskManager(b.db_file).bind_project('Demo', repo_b)
        code, listed = self.bridge(b, 'list', '--project', 'Demo', '--status', 'pending')
        self.assertEqual(code, 0, listed)
        self.assertEqual([t['id'] for t in listed['result']['tasks']], [task['id']])
        TaskManager(a.db_file).bind_project('Demo', repo_a)
        code, claimed = self.bridge(a, 'claim', '--project', 'Demo', '--repo', str(repo_a), '--id', task['id'],
                                    '--revision', str(task['revision']), '--owner', 'pc-a')
        self.assertEqual(code, 0, claimed)
        self.assertEqual(claimed['sync_warnings'], [])
        # Computer B still lists the old revision; its claim syncs first and loses.
        code, lost = self.bridge(b, 'claim', '--project', 'Demo', '--repo', str(repo_b), '--id', task['id'],
                                 '--revision', str(task['revision']), '--owner', 'pc-b')
        self.assertEqual(code, 2, lost)
        remote = TaskManager(b.db_file).tasks[0]
        self.assertEqual((remote['status'], remote['owner']), ('in_progress', 'pc-a'))
        claim = claimed['result']
        code, reported = self.bridge(a, 'report', '--project', 'Demo', '--repo', str(repo_a), '--id', task['id'],
                                     '--revision', str(claim['revision']), '--token', claim['claim_token'],
                                     '--status', 'completed', '--summary', 'Bitti', '--evidence', 'tests passed')
        self.assertEqual(code, 0, reported)
        self.service(b).run()
        self.assertTrue(TaskManager(b.db_file).tasks[0]['completed'])

    def test_bridge_works_offline_with_a_warning(self):
        a = self.store('a')
        self.sign_in(a)
        repo = self.root / 'repo'
        repo.mkdir()
        (repo / '.git').mkdir()
        task = a.add_task('Çevrimdışı', 'Demo')
        a.bind_project('Demo', repo)

        def offline(request, timeout):
            raise urllib.error.URLError('no route')
        self.backend = offline
        code, claimed = self.bridge(a, 'claim', '--project', 'Demo', '--repo', str(repo), '--id', task['id'],
                                    '--revision', str(task['revision']), '--owner', 'pc-a')
        self.assertEqual(code, 0, claimed)
        self.assertEqual(len(claimed['sync_warnings']), 2)
        self.assertTrue(all(w.startswith('Bulut senkronu: Eşitlenemedi') for w in claimed['sync_warnings']))

    @unittest.skipUnless(os.name == 'nt', 'Windows Credential Manager')
    def test_windows_credential_round_trip(self):
        store = cloud_sync.WindowsCredentials()
        target = 'TaskFlow test ' + uuid.uuid4().hex
        try:
            self.assertIsNone(store.read(target))
            store.write(target, json.dumps({'refresh_token': 'şifre-değil'}))
            self.assertEqual(json.loads(store.read(target))['refresh_token'], 'şifre-değil')
            with self.assertRaises(ValueError):
                store.write(target, 'x' * 3000)
        finally:
            store.delete(target)
        self.assertIsNone(store.read(target))
        store.delete(target)

    def test_window_shows_status_and_syncs_after_local_edits(self):
        from PyQt5.QtWidgets import QApplication
        from app_gui import CloudSyncDialog, TaskFlowApp
        app = QApplication.instance() or QApplication(sys.argv)
        a, b = self.store('a', config=None), self.store('b')
        self.sign_in(b)
        win = TaskFlowApp(start_minimized=True, task_manager=a, setup_autostart=False, cloud=self.service(a))

        def settle():
            deadline = time.time() + 10
            while time.time() < deadline:
                app.processEvents()
                if not win._cloud_running:
                    return
                time.sleep(0.02)
            self.fail('sync did not finish')
        try:
            self.assertFalse(win.cloud_timer.isActive())
            self.assertIn('kapalı', win.cloud_btn.toolTip())
            self.assertTrue(win.cloud_btn.isHidden() and not win.sparkle_lbl.isHidden())
            dialog = CloudSyncDialog(win)
            self.assertTrue(dialog.off_btn.isHidden())
            dialog.deleteLater()
            win.set_cloud_config(dict(CONFIG))
            self.assertTrue(win.cloud_timer.isActive())
            win.start_cloud_sync()
            settle()
            self.assertEqual(win.cloud_status['state'], 'ok')
            self.assertIn('Eşitlendi', win.cloud_btn.toolTip())
            self.assertTrue(win.sparkle_lbl.isHidden() and not win.cloud_btn.isHidden())
            win.task_input.setText('Pencereden görev')
            win._add_task()
            win._poll_external_changes()
            settle()
            self.service(b).run()
            self.assertIn('Pencereden görev', [t['title'] for t in TaskManager(b.db_file).tasks])
            dialog = CloudSyncDialog(win)
            self.assertEqual(dialog.url_field.text(), URL)
            dialog._turn_off()
            self.assertFalse(win.cloud_timer.isActive())
            self.assertIsNone(self.credentials.read(cloud_sync.credential_target(CONFIG)))
            self.assertEqual((win.width(), win.height()), (440, 640))
        finally:
            win.tray_icon.hide()
            win.sync_timer.stop()
            win.cloud_timer.stop()
            win.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
