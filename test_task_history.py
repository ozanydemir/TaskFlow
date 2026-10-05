"""Archive, delivery and durable-history checks use disposable demo stores only."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from task_manager import TaskConflict, TaskManager


class TestTaskHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = TaskManager(self.root / 'data.sqlite3')
        self.repo = self.root / 'repo'
        (self.repo / '.git').mkdir(parents=True)
        self.brain = self.root / 'brain'
        self.brain.mkdir()
        (self.brain / 'PROJECT_CONTEXT.md').write_text('# Demo', encoding='utf-8')
        self.manager.add_project('Demo')
        self.manager.bind_project('Demo', self.repo, self.brain)

    def tearDown(self):
        self.temp.cleanup()

    def complete(self, delivery=None, status='completed'):
        task = self.manager.add_task('Demo fix', 'Demo')
        claim = self.manager.claim_task('Demo', task['id'], task['revision'], 'demo-session')
        return self.manager.report_task('Demo', task['id'], claim['revision'], claim['claim_token'],
                                        status, 'Fixed demo behavior', 'Demo checks passed', delivery=delivery)

    def test_archive_preserves_results_notes_delivery_and_restores_without_requeue(self):
        task = self.complete('published')
        self.manager.edit_notes(task['id'], 'A note')
        previous = self.manager.get_tasks('Demo')[0]
        self.assertEqual(self.manager.archive_completed('Demo'), 1)
        self.assertEqual(self.manager.get_tasks('Demo'), [])
        archived = TaskManager(self.manager.db_file).get_tasks('Demo', archived=True)[0]
        for field in ('id', 'result', 'history', 'notes', 'delivery', 'completed_at'):
            self.assertEqual(archived[field], previous[field])
        restored = self.manager.restore_task(task['id'])
        self.assertTrue(restored['completed'])
        self.assertEqual(restored['delivery'], 'published')
        self.assertNotIn('archived_at', restored)

    def test_archive_is_project_scoped_excludes_review_and_is_idempotent(self):
        self.complete()
        self.complete(status='needs_review')
        other = self.manager.add_task('Other completed', 'Other')
        self.manager.toggle_task(other['id'])
        self.assertEqual(self.manager.clear_completed('Demo'), 1)
        self.assertEqual(self.manager.clear_completed('Demo'), 0)
        self.assertEqual(self.manager.get_stats('Demo'), (1, 0))
        self.assertEqual(self.manager.get_stats('Other'), (1, 1))
        self.assertEqual(len(self.manager.get_tasks('Demo', archived=True)), 1)

    def test_parallel_archiving_retains_each_result_once(self):
        self.complete()
        self.complete()
        managers = [TaskManager(self.manager.db_file), TaskManager(self.manager.db_file)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            counts = list(pool.map(lambda m: m.archive_completed('Demo'), managers))
        self.assertEqual(sum(counts), 2)
        restored = TaskManager(self.manager.db_file)
        self.assertEqual(len(restored.get_tasks('Demo', archived=True)), 2)
        self.assertEqual(sum(e['kind'] == 'archived' for e in restored.get_history('Demo')), 2)

    def test_archived_task_cannot_be_claimed_with_current_or_old_revision(self):
        task = self.complete()
        self.manager.archive_completed('Demo')
        archived = self.manager.get_tasks('Demo', archived=True)[0]
        for revision in (task['revision'], archived['revision']):
            with self.assertRaises(TaskConflict):
                self.manager.claim_task('Demo', task['id'], revision, 'another-session')

    def test_journal_and_brain_survive_archive_delete_and_project_unbind(self):
        manual = self.brain / 'TASKFLOW_HISTORY.md'
        manual.write_text('# Notes\nKeep manual history.\n', encoding='utf-8')
        task = self.complete()
        self.manager.archive_completed('Demo')
        self.assertNotIn(task['id'], (self.brain / 'TODO.md').read_text(encoding='utf-8'))
        self.manager.delete_task(task['id'])
        history = self.manager.get_history('Demo')
        self.assertEqual([e['kind'] for e in history], ['report', 'archived', 'deleted'])
        before = manual.read_bytes()
        self.assertIn(b'Keep manual history.', before)
        self.assertIn(b'Demo checks passed', before)
        self.manager.export_project('Demo')
        self.assertEqual(manual.read_bytes(), before)
        self.manager.delete_project('Demo')
        self.assertEqual(manual.read_bytes(), before)
        with closing(sqlite3.connect(self.manager.db_file)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM task_events').fetchone()[0], 3)

    def test_corrupt_journal_mirror_preserves_primary_events_and_retries(self):
        binding = self.manager.bindings['Demo']
        target = self.brain / 'TASKFLOW_HISTORY.md'
        broken = '<!-- taskflow-history:begin ' + binding['project_id'] + ' -->\nmanual'
        target.write_text(broken, encoding='utf-8')
        self.complete()
        self.assertTrue(self.manager.sync_errors)
        self.assertEqual(target.read_text(encoding='utf-8'), broken)
        self.assertEqual(len(self.manager.get_history('Demo')), 1)
        target.write_text('# Recovered manual note\n', encoding='utf-8')
        self.manager.export_project('Demo')
        content = target.read_text(encoding='utf-8')
        self.assertIn('Recovered manual note', content)
        self.assertIn('Demo checks passed', content)

    def test_legacy_v1_migration_is_additive_and_imports_prior_results_once(self):
        old = self.root / 'old.sqlite3'
        payload = {'id': 'old-task', 'title': 'Legacy task', 'project': 'Demo', 'completed': True,
                   'status': 'completed', 'revision': 3, 'notes': 'Preserved', 'completed_at': '01.10.2026 12:00',
                   'result': {'status': 'completed', 'summary': 'Old work', 'evidence': 'Old check',
                              'reported_at': '01.10.2026 12:00', 'owner': 'old-session'}}
        with closing(sqlite3.connect(old)) as conn, conn:
            conn.executescript("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                               "CREATE TABLE tasks (id TEXT PRIMARY KEY, position INTEGER NOT NULL, payload TEXT NOT NULL);"
                               "CREATE TABLE projects (name TEXT PRIMARY KEY, position INTEGER NOT NULL, binding TEXT);"
                               "CREATE TABLE settings (key TEXT PRIMARY KEY, payload TEXT NOT NULL);"
                               "INSERT INTO meta VALUES ('schema','1'); INSERT INTO meta VALUES ('change','0');"
                               "INSERT INTO projects VALUES ('Demo',0,NULL); INSERT INTO settings VALUES ('autostart','false');")
            conn.execute('INSERT INTO tasks VALUES (?,?,?)', ('old-task', 0, json.dumps(payload)))
        manager = TaskManager(old)
        self.assertEqual(manager.tasks[0], payload)
        self.assertFalse(manager.settings['autostart'])
        self.assertNotIn('delivery', manager.tasks[0])
        self.assertEqual(len(manager.get_history('Demo')), 1)
        manager = TaskManager(old)
        self.assertEqual(len(manager.get_history('Demo')), 1)
        manager.bind_project('Demo', self.repo, self.brain)
        self.assertIn('Old check', (self.brain / 'TASKFLOW_HISTORY.md').read_text(encoding='utf-8'))

    def test_default_report_is_local_published_is_explicit_and_review_is_preserved(self):
        task = self.complete()
        self.assertEqual(task['delivery'], 'local')
        self.assertEqual(task['result']['delivery'], 'local')
        published = self.manager.mark_published('Demo', task['id'], task['revision'], 'Demo release verified')
        self.assertEqual(published['delivery'], 'published')
        review = self.complete('published', status='needs_review')
        self.assertFalse(review['completed'])
        self.assertEqual(review['delivery'], 'published')

    def test_publication_rejects_missing_evidence_wrong_project_and_stale_revision(self):
        task = self.complete()
        with self.assertRaises(ValueError):
            self.manager.mark_published('Demo', task['id'], task['revision'], ' ')
        with self.assertRaises(TaskConflict):
            self.manager.mark_published('Other', task['id'], task['revision'], 'Check')
        self.manager.edit_notes(task['id'], 'User edited')
        with self.assertRaises(TaskConflict):
            self.manager.mark_published('Demo', task['id'], task['revision'], 'Check')
        self.assertEqual(self.manager.get_tasks('Demo')[0]['delivery'], 'local')

    def test_report_rejects_published_without_evidence_or_for_blocked_work(self):
        task = self.manager.add_task('Unverified demo task', 'Demo')
        claim = self.manager.claim_task('Demo', task['id'], task['revision'], 'demo')
        for status, evidence in [('needs_review', ''), ('blocked', 'checked')]:
            with self.assertRaises(ValueError):
                self.manager.report_task('Demo', task['id'], claim['revision'], claim['claim_token'],
                                         status, 'A summary', evidence, delivery='published')
        self.assertEqual(self.manager.get_tasks('Demo')[0]['status'], 'in_progress')

    def test_requeue_resets_current_publication_but_retains_historical_evidence(self):
        task = self.complete()
        task = self.manager.mark_published('Demo', task['id'], task['revision'], 'Published demo v1')
        self.manager.requeue_task(task['id'])
        current = self.manager.get_tasks('Demo')[0]
        self.assertEqual(current['delivery'], 'unspecified')
        self.assertNotIn('publication_evidence', current)
        self.assertTrue(any(e['task'].get('publication_evidence') == 'Published demo v1'
                            for e in self.manager.get_history('Demo')))

    def test_cli_delivery_history_publish_and_archived_scope(self):
        command = [sys.executable, str(Path(__file__).with_name('taskflow_agent.py')), '--db', self.manager.db_file]
        def run(*args):
            result = subprocess.run(command + list(args), capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)['result']
        task = self.manager.add_task('CLI demo', 'Demo')
        scope = ['--project', 'Demo', '--repo', str(self.repo), '--id', task['id']]
        claim = run('claim', *scope, '--revision', '1', '--owner', 'demo')
        completed = run('report', *scope, '--revision', str(claim['revision']), '--token', claim['claim_token'],
                        '--status', 'completed', '--delivery', 'not_applicable', '--summary', 'Done', '--evidence', 'Checked')
        self.assertEqual(completed['delivery'], 'not_applicable')
        published = run('publish', *scope, '--revision', str(completed['revision']), '--evidence', 'Published demo')
        self.assertEqual(published['delivery'], 'published')
        self.manager.archive_completed('Demo')
        self.assertEqual(run('list', '--project', 'Demo')['tasks'], [])
        self.assertEqual(len(run('list', '--project', 'Demo', '--archived')['tasks']), 1)
        events = run('history', '--project', 'Demo')['events']
        self.assertEqual(len(events), 3)
        self.assertNotIn('claim_token', json.dumps(events))

    def test_gui_archive_restore_and_delivery_labels_keep_compact_window(self):
        from PyQt5.QtWidgets import QApplication
        from app_gui import TaskArchiveDialog, TaskFlowApp
        app = QApplication.instance() or QApplication([])
        task = self.complete()
        win = TaskFlowApp(start_minimized=True, task_manager=self.manager, setup_autostart=False)
        try:
            win.task_input.setText('Unsaved demo text')
            card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))
            self.assertTrue(card.date_label.text().startswith('Yerelde tamamlandı'))
            self.manager.archive_completed('Demo')
            win._refresh_tasks()
            self.assertEqual(win.task_list_widget.count(), 0)
            dialog = TaskArchiveDialog(self.manager, 'Demo', win)
            self.assertEqual(dialog.list.count(), 1)
            self.assertIn('Demo checks passed', dialog.details.toPlainText())
            dialog._restore()
            self.assertEqual(dialog.list.count(), 0)
            win._refresh_tasks()
            self.assertEqual(win.task_list_widget.count(), 1)
            self.assertEqual(win.task_input.text(), 'Unsaved demo text')
            self.assertEqual((win.width(), win.height()), (440, 640))
            self.assertEqual((win.minimumWidth(), win.minimumHeight()), (340, 460))
            dialog.deleteLater()
        finally:
            win.sync_timer.stop()
            win.tray_icon.hide()
            win.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
