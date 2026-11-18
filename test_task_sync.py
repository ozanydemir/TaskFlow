"""Multi-device sync checks: two disposable stores share an in-memory server. No network is used."""
import json
import tempfile
import unittest
from pathlib import Path

from task_manager import TaskConflict, TaskManager
from task_sync import MemoryServer, SyncEngine


class TestTaskSync(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = MemoryServer()
        self.a = TaskManager(self.root / 'a' / 'data.sqlite3')
        self.b = TaskManager(self.root / 'b' / 'data.sqlite3')
        self.sync_a = SyncEngine(self.a, self.server)
        self.sync_b = SyncEngine(self.b, self.server)

    def tearDown(self):
        self.temp.cleanup()

    def settle(self):
        for _ in range(3):
            self.sync_a.sync()
            self.sync_b.sync()

    def task(self, manager, title):
        return next(t for t in manager.tasks if t['title'] == title)

    def cloud_state(self, manager):
        with manager._connection() as conn:
            return SyncEngine(manager, self.server)._local_records(conn)

    def assert_converged(self):
        self.assertEqual(self.cloud_state(self.a), self.cloud_state(self.b))

    def brain(self, name):
        repo, brain = self.root / name / 'repo', self.root / name / 'brain'
        (repo / '.git').mkdir(parents=True)
        brain.mkdir()
        (brain / 'PROJECT_CONTEXT.md').write_text('# Demo', encoding='utf-8')
        return repo, brain

    def test_tasks_notes_and_projects_reach_the_other_device(self):
        task = self.a.add_task('Ortak görev', 'Demo')
        self.settle()
        self.assertEqual(self.b.projects, ['Demo'])
        self.assertEqual(self.b.project_ids, self.a.project_ids)
        self.b.edit_notes(task['id'], 'İkinci bilgisayardan not')
        self.settle()
        self.assertEqual(self.task(self.a, 'Ortak görev')['notes'], 'İkinci bilgisayardan not')
        self.assertEqual(self.task(self.a, 'Ortak görev')['project'], 'Demo')
        self.assert_converged()

    def test_different_fields_merge_without_conflict(self):
        task = self.a.add_task('Başlık', 'Demo')
        self.settle()
        self.a.edit_task(task['id'], 'Yeni başlık')
        self.b.edit_notes(task['id'], 'Not')
        self.settle()
        for manager in (self.a, self.b):
            merged = self.task(manager, 'Yeni başlık')
            self.assertEqual(merged['notes'], 'Not')
            self.assertFalse(any(e['kind'] == 'sync_conflict' for e in manager.get_history('Demo')))
        self.assert_converged()

    def test_same_field_conflict_keeps_first_version_and_journals_the_other(self):
        task = self.a.add_task('Görev', 'Demo')
        self.settle()
        self.a.edit_notes(task['id'], 'A notu')
        self.b.edit_notes(task['id'], 'B notu')
        self.settle()
        for manager in (self.a, self.b):
            self.assertEqual(self.task(manager, 'Görev')['notes'], 'A notu')
            conflicts = [e for e in manager.get_history('Demo') if e['kind'] == 'sync_conflict']
            self.assertEqual([e['task']['notes'] for e in conflicts], ['B notu'])
        self.assert_converged()

    def test_competing_claims_keep_one_and_reject_the_other_report(self):
        task = self.a.add_task('Agent işi', 'Demo')
        self.settle()
        claim_a = self.a.claim_task('Demo', task['id'], task['revision'], 'agent-a')
        claim_b = self.b.claim_task('Demo', task['id'], task['revision'], 'agent-b')
        self.settle()
        self.assertEqual(self.task(self.b, 'Agent işi')['owner'], 'agent-a')
        with self.assertRaises(TaskConflict):
            self.b.report_task('Demo', task['id'], claim_b['revision'], claim_b['claim_token'],
                               'completed', 'B', 'B checks')
        self.a.report_task('Demo', task['id'], claim_a['revision'], claim_a['claim_token'],
                           'completed', 'A finished', 'A checks passed')
        self.settle()
        done = self.task(self.b, 'Agent işi')
        self.assertTrue(done['completed'])
        self.assertEqual(done['result']['summary'], 'A finished')
        self.assertEqual([e['kind'] for e in self.b.get_history('Demo')], ['report'])
        self.assert_converged()

    def test_edit_after_remote_claim_requeues_like_a_local_edit(self):
        task = self.a.add_task('Agent işi', 'Demo')
        self.settle()
        claim = self.a.claim_task('Demo', task['id'], task['revision'], 'agent-a')
        self.b.edit_notes(task['id'], 'Ek bilgi')
        self.settle()
        current = self.task(self.a, 'Agent işi')
        self.assertEqual((current['status'], current['notes']), ('pending', 'Ek bilgi'))
        with self.assertRaises(TaskConflict):
            self.a.report_task('Demo', task['id'], claim['revision'], claim['claim_token'],
                               'completed', 'Old', 'Old checks')
        self.assert_converged()

    def test_deletion_wins_and_keeps_the_concurrent_edit_in_history(self):
        task = self.a.add_task('Silinecek', 'Demo')
        kept = self.a.add_task('Kalacak', 'Demo')
        self.settle()
        self.a.delete_task(task['id'])
        self.b.edit_notes(task['id'], 'Geç kalan not')
        self.settle()
        for manager in (self.a, self.b):
            self.assertEqual([t['id'] for t in manager.tasks], [kept['id']])
        kinds = [e['kind'] for e in self.b.get_history('Demo')]
        self.assertIn('deleted', kinds)
        self.assertIn('sync_conflict', kinds)
        self.assert_converged()

    def test_archive_restore_and_history_sync_once(self):
        task = self.a.add_task('Bitti', 'Demo')
        self.a.toggle_task(task['id'])
        self.a.archive_completed('Demo')
        self.settle()
        self.assertEqual([t['id'] for t in self.b.get_tasks('Demo', archived=True)], [task['id']])
        self.b.restore_task(task['id'])
        self.settle()
        self.settle()
        self.assertEqual(self.a.get_tasks('Demo', archived=True), [])
        kinds = [e['kind'] for e in self.a.get_history('Demo')]
        self.assertEqual(sorted(kinds), ['archived', 'manual_completion', 'restored'])
        self.assertEqual(sorted(kinds), sorted(e['kind'] for e in self.b.get_history('Demo')))

    def test_same_project_on_both_devices_is_adopted_with_markers(self):
        self.a.add_task('A görevi', 'Demo')
        self.sync_a.sync()
        repo, brain = self.brain('b')
        self.b.add_project('Demo')
        self.b.bind_project('Demo', repo, brain)
        self.b.add_task('B görevi', 'Demo')
        old = self.b.bindings['Demo']['project_id']
        self.settle()
        uid = self.a.project_ids['Demo']
        self.assertNotEqual(uid, old)
        self.assertEqual(self.b.project_ids, {'Demo': uid})
        self.assertEqual(self.b.bindings['Demo']['project_id'], uid)
        self.assertEqual(self.b.bindings['Demo']['repo_path'], str(repo.resolve()))
        self.assertNotIn('Demo', self.a.bindings)
        todo = (brain / 'TODO.md').read_text(encoding='utf-8')
        self.assertEqual(todo.count('taskflow:begin'), 1)
        self.assertIn(uid, todo)
        self.assertNotIn(old, todo)
        self.assertIn('A görevi', todo)
        self.assertEqual(sorted(t['title'] for t in self.a.get_tasks('Demo')), ['A görevi', 'B görevi'])
        self.assert_converged()

    def test_project_deletion_and_rename_propagate(self):
        self.a.add_task('Görev', 'Eski')
        self.a.add_project('Kalan')
        self.settle()
        with self.a._connection(write=True) as conn:
            self.sync_a._rename(conn, 'Eski', 'Yeni')
        self.a.load()
        self.settle()
        self.assertEqual(sorted(self.b.projects), ['Kalan', 'Yeni'])
        self.assertEqual(self.task(self.b, 'Görev')['project'], 'Yeni')
        self.b.delete_project('Yeni')
        self.settle()
        self.assertEqual(self.a.projects, ['Kalan'])
        self.assertIsNone(self.task(self.a, 'Görev')['project'])
        self.assert_converged()

    def test_settings_and_bindings_stay_on_the_device(self):
        repo, brain = self.brain('a')
        self.a.add_project('Demo')
        self.a.bind_project('Demo', repo, brain)
        self.a.settings['always_on_top'] = True
        self.a.save()
        self.settle()
        self.assertEqual(self.b.projects, ['Demo'])
        self.assertEqual(self.b.bindings, {})
        self.assertFalse(self.b.settings['always_on_top'])
        for record in self.server.records.values():
            self.assertNotIn(str(repo.resolve()), json.dumps(record, ensure_ascii=False))

    def test_offline_edits_survive_and_sync_later(self):
        class Offline:
            def __getattr__(self, name):
                raise OSError('offline')
        task = self.a.add_task('Çevrimdışı', 'Demo')
        offline = SyncEngine(self.a, Offline())
        with self.assertRaises(OSError):
            offline.sync()
        self.a.edit_notes(task['id'], 'Bağlantı yokken')
        self.assertEqual(self.server.records, {})
        self.settle()
        self.assertEqual(self.task(self.b, 'Çevrimdışı')['notes'], 'Bağlantı yokken')

    def test_repeated_sync_is_quiet(self):
        self.a.add_task('Görev', 'Demo')
        self.settle()
        with self.b._connection() as conn:
            change = conn.execute("SELECT value FROM meta WHERE key='change'").fetchone()[0]
        seq = self.server.seq
        self.assertFalse(self.sync_b.sync())
        self.assertFalse(self.sync_a.sync())
        self.assertEqual(self.server.seq, seq)
        with self.b._connection() as conn:
            self.assertEqual(conn.execute("SELECT value FROM meta WHERE key='change'").fetchone()[0], change)


    def test_large_first_join_uses_batches_and_pages(self):
        SyncEngine.RECORD_BATCH, SyncEngine.EVENT_BATCH = 7, 5
        self.addCleanup(setattr, SyncEngine, 'RECORD_BATCH', 200)
        self.addCleanup(setattr, SyncEngine, 'EVENT_BATCH', 500)
        pull = self.server.pull
        self.server.pull = lambda cursor: pull(cursor, limit=4)
        for index in range(30):
            task = self.a.add_task('Görev {}'.format(index), 'Demo')
            if index % 3 == 0:
                self.a.toggle_task(task['id'])
        self.settle()
        self.assertEqual(len(self.b.tasks), 30)
        self.assertEqual(len(self.b.get_history('Demo')), 10)
        self.assert_converged()

if __name__ == '__main__':
    unittest.main()
