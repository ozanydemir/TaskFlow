"""Integration checks use synthetic data and never touch the user's store or startup settings."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from task_manager import TaskConflict, TaskManager
from taskflow_agent import agent_prompt


class TestAgentBridge(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.json = self.root / 'data.json'
        self.manager = TaskManager(self.json)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / '.git').mkdir()
        self.brain = self.root / 'brain'
        self.brain.mkdir()
        (self.brain / 'PROJECT_CONTEXT.md').write_text('# Demo', encoding='utf-8')
        self.manager.add_project('Demo')

    def tearDown(self):
        self.temp.cleanup()

    def bind(self):
        return self.manager.bind_project('Demo', self.repo, self.brain)

    def claim(self, task):
        return self.manager.claim_task('Demo', task['id'], task['revision'], 'test-session')

    def report(self, claim, status='completed', evidence='Unit tests: passed'):
        return self.manager.report_task('Demo', claim['id'], claim['revision'], claim['claim_token'], status, 'Demo fix', evidence)

    def test_json_migration_retains_ids_notes_preferences_and_original_bytes(self):
        source = self.root / 'legacy.json'
        data = {'projects': ['Demo'], 'tasks': [{'id': 'old-id', 'title': 'Başlık', 'project': 'Demo',
                 'completed': True, 'completed_at': '01.10.2026 10:20', 'notes': 'Özel not', 'extra': 42}],
                'settings': {'always_on_top': True, 'autostart': False}}
        original = json.dumps(data, ensure_ascii=False).encode('utf-8')
        source.write_bytes(original)
        manager = TaskManager(source)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(source.with_name('legacy.json.pre-sqlite.bak').read_bytes(), original)
        self.assertEqual(manager.tasks[0]['id'], 'old-id')
        self.assertEqual(manager.tasks[0]['notes'], 'Özel not')
        self.assertEqual(manager.tasks[0]['extra'], 42)
        self.assertEqual(manager.tasks[0]['status'], 'completed')
        self.assertFalse(manager.settings['autostart'])
        manager.add_task('New')
        self.assertEqual(len(TaskManager(source).tasks), 2)
        self.assertEqual(source.read_bytes(), original)

    def test_invalid_and_duplicate_legacy_records_never_become_empty_success(self):
        for index, content in enumerate(['{invalid', json.dumps({'projects': [], 'tasks': [{'id': 'same', 'title': 'a'}, {'id': 'same', 'title': 'b'}]})]):
            source = self.root / f'bad{index}.json'
            source.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                TaskManager(source)
            self.assertEqual(source.read_text(encoding='utf-8'), content)

    def test_stale_gui_settings_save_preserves_external_result_and_preferences(self):
        task = self.manager.add_task('Fix', 'Demo')
        agent = TaskManager(self.json)
        claim = agent.claim_task('Demo', task['id'], task['revision'], 'session')
        agent.settings['autostart'] = False
        agent.save()
        agent.report_task('Demo', claim['id'], claim['revision'], claim['claim_token'], 'completed', 'Fixed', 'tests passed')
        self.manager.settings['always_on_top'] = True
        self.manager.save()
        restored = TaskManager(self.json)
        self.assertEqual(restored.tasks[0]['status'], 'completed')
        self.assertTrue(restored.settings['always_on_top'])
        self.assertFalse(restored.settings['autostart'])

    def test_simultaneous_claim_has_exactly_one_winner(self):
        task = self.manager.add_task('Fix', 'Demo')
        first, second = TaskManager(self.json), TaskManager(self.json)
        def claim(manager):
            try:
                return manager.claim_task('Demo', task['id'], task['revision'], 'session')['claim_token']
            except TaskConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, [first, second]))
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_parallel_additions_are_all_retained(self):
        first, second = TaskManager(self.json), TaskManager(self.json)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda manager: manager.add_task('Task', 'Demo'), [first, second]))
        self.assertEqual(len(TaskManager(self.json).tasks), 2)

    def test_edit_or_manual_completion_invalidates_old_agent_report(self):
        for operation in ('title', 'notes', 'complete', 'requeue'):
            task = self.manager.add_task(operation, 'Demo')
            claim = self.claim(task)
            if operation == 'title':
                self.manager.edit_task(task['id'], 'Edited')
            elif operation == 'notes':
                self.manager.edit_notes(task['id'], 'Changed requirement')
            elif operation == 'complete':
                self.manager.toggle_task(task['id'])
            else:
                self.manager.requeue_task(task['id'])
            with self.assertRaises(TaskConflict):
                self.report(claim)

    def test_reports_reject_other_project_wrong_token_missing_evidence(self):
        task = self.manager.add_task('Fix', 'Demo')
        claim = self.claim(task)
        with self.assertRaises(TaskConflict):
            self.manager.report_task('Other', task['id'], claim['revision'], claim['claim_token'], 'completed', 'Fix', 'passed')
        with self.assertRaises(TaskConflict):
            self.manager.report_task('Demo', task['id'], claim['revision'], 'wrong', 'completed', 'Fix', 'passed')
        with self.assertRaises(ValueError):
            self.report(claim, evidence='')
        self.assertEqual(TaskManager(self.json).tasks[0]['status'], 'in_progress')
        self.assertEqual(self.report(claim)['status'], 'completed')
        with self.assertRaises(TaskConflict):
            self.report(claim)

    def test_user_review_prevents_automatic_tick_and_can_be_accepted_manually(self):
        task = self.manager.add_task('Visual fix', 'Demo')
        self.manager.set_review_required(task['id'], True)
        task = self.manager.tasks[0]
        result = self.report(self.claim(task))
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['completed'])
        self.manager.toggle_task(task['id'])
        self.assertTrue(self.manager.tasks[0]['completed'])
        self.assertEqual(len(self.manager.tasks[0]['history']), 1)

    def test_blocked_task_can_be_requeued_without_losing_report(self):
        task = self.manager.add_task('Fix', 'Demo')
        result = self.report(self.claim(task), status='blocked', evidence='')
        self.assertEqual(result['status'], 'blocked')
        self.manager.requeue_task(task['id'])
        self.assertEqual(self.manager.tasks[0]['status'], 'pending')
        self.assertEqual(self.manager.tasks[0]['result']['summary'], 'Demo fix')

    def test_stale_full_snapshot_cannot_overwrite_an_agent(self):
        task = self.manager.add_task('Fix', 'Demo')
        agent = TaskManager(self.json)
        agent.claim_task('Demo', task['id'], task['revision'], 'session')
        self.manager.tasks[0]['title'] = 'stale edit'
        with self.assertRaises(TaskConflict):
            self.manager.save()
        self.assertEqual(TaskManager(self.json).tasks[0]['status'], 'in_progress')

    def test_projection_is_automatic_preserves_manual_content_and_is_project_scoped(self):
        target = self.brain / 'TODO.md'
        target.write_text('# Existing\n\n- [ ] Manual item\n', encoding='utf-8')
        self.bind()
        task = self.manager.add_task('Demo task', 'Demo')
        self.manager.add_task('Hidden other task', 'Other')
        self.manager.edit_notes(task['id'], 'Note with <!-- markup -->\nsecond line')
        self.report(self.claim(self.manager.get_tasks('Demo')[0]))
        output = target.read_text(encoding='utf-8')
        self.assertIn('- [ ] Manual item', output)
        self.assertIn('- [x] Demo task', output)
        self.assertIn('Unit tests: passed', output)
        self.assertNotIn('Hidden other task', output)
        self.assertIn('&lt;!--', output)
        self.assertEqual(output.count('<!-- taskflow:begin'), 1)
        self.manager.export_project('Demo')
        self.assertEqual(target.read_text(encoding='utf-8'), output)

    def test_corrupt_projection_is_preserved_and_database_write_still_succeeds(self):
        binding = self.bind()
        target = self.brain / 'TODO.md'
        broken = '<!-- taskflow:begin ' + binding['project_id'] + ' -->\nmanual'
        target.write_text(broken, encoding='utf-8')
        self.manager.add_task('Persist despite mirror error', 'Demo')
        self.assertTrue(self.manager.sync_errors)
        self.assertEqual(target.read_text(encoding='utf-8'), broken)
        self.assertEqual(TaskManager(self.json).tasks[0]['title'], 'Persist despite mirror error')

    def test_binding_validates_paths_and_prevents_duplicate_repo(self):
        with self.assertRaises(ValueError):
            self.manager.bind_project('Demo', self.brain)
        with self.assertRaises(ValueError):
            self.manager.bind_project('Demo', self.repo, self.repo)
        self.bind()
        self.manager.add_project('Other')
        with self.assertRaises(ValueError):
            self.manager.bind_project('Other', self.repo)

    def test_deleted_project_detaches_only_its_projection_and_preserves_completed_tasks(self):
        (self.brain / 'TODO.md').write_text('# Manual\n- [ ] Keep this\n', encoding='utf-8')
        self.bind()
        task = self.manager.add_task('Completed task', 'Demo')
        self.manager.toggle_task(task['id'])
        self.manager.delete_project('Demo')
        self.assertTrue(self.manager.tasks[0]['completed'])
        self.assertIsNone(self.manager.tasks[0]['project'])
        content = (self.brain / 'TODO.md').read_text(encoding='utf-8')
        self.assertIn('Keep this', content)
        self.assertNotIn('taskflow:begin', content)

    def test_rebinding_detaches_previous_projection_and_invalidates_active_claims(self):
        self.bind()
        task = self.manager.add_task('Task', 'Demo')
        claim = self.claim(task)
        new_repo = self.root / 'new-repo'
        new_repo.mkdir()
        (new_repo / '.git').mkdir()
        self.manager.bind_project('Demo', new_repo)
        self.assertNotIn('taskflow:begin', (self.brain / 'TODO.md').read_text(encoding='utf-8'))
        self.assertEqual(self.manager.tasks[0]['status'], 'pending')
        with self.assertRaises(TaskConflict):
            self.report(claim)

    def test_cli_round_trip_and_repo_scope(self):
        self.bind()
        task = self.manager.add_task('CLI task', 'Demo')
        script = Path(__file__).with_name('taskflow_agent.py')
        def invoke(*args):
            return subprocess.run([sys.executable, str(script), '--db', self.manager.db_file, *args], capture_output=True, encoding='utf-8')
        listed = invoke('list', '--project', 'Demo', '--status', 'pending')
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(json.loads(listed.stdout)['result']['tasks'][0]['id'], task['id'])
        base = ['--project', 'Demo', '--repo', str(self.repo), '--id', task['id']]
        wrong = invoke('claim', '--project', 'Demo', '--repo', str(self.brain), '--id', task['id'], '--revision', '1', '--owner', 'session')
        self.assertEqual(wrong.returncode, 2)
        claimed = invoke('claim', *base, '--revision', '1', '--owner', 'session')
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        claim = json.loads(claimed.stdout)['result']
        listed = json.loads(invoke('list', '--project', 'Demo').stdout)['result']['tasks'][0]
        self.assertNotIn('claim_token', listed)
        reported = invoke('report', *base, '--revision', str(claim['revision']), '--token', claim['claim_token'], '--status', 'completed', '--summary', 'Fixed', '--evidence', 'passed')
        self.assertEqual(reported.returncode, 0, reported.stderr)
        self.assertTrue(TaskManager(self.json).tasks[0]['completed'])

    def test_installer_copies_both_tools_without_touching_user_data(self):
        import installer
        package = self.root / 'package'
        (package / 'payload').mkdir(parents=True)
        (package / 'payload' / 'TaskFlow.exe').write_bytes(b'demo-app')
        (package / 'payload' / 'TaskFlowAgent.exe').write_bytes(b'demo-agent')
        destination = self.root / 'installed'
        before = Path(self.manager.db_file).read_bytes()
        with patch('installer.bundled_path', side_effect=lambda name: package / name), patch('installer.install_root', return_value=destination), patch('installer.create_shortcut') as shortcut:
            installed = installer.install_taskflow()
        self.assertEqual(installed.read_bytes(), b'demo-app')
        self.assertEqual((destination / 'TaskFlowAgent.exe').read_bytes(), b'demo-agent')
        self.assertEqual(shortcut.call_count, 2)
        self.assertEqual(Path(self.manager.db_file).read_bytes(), before)

    def test_missing_agent_payload_preserves_existing_application(self):
        import installer
        package = self.root / 'package'
        (package / 'payload').mkdir(parents=True)
        (package / 'payload' / 'TaskFlow.exe').write_bytes(b'new-app')
        destination = self.root / 'installed'
        destination.mkdir()
        (destination / 'TaskFlow.exe').write_bytes(b'existing-app')
        with patch('installer.bundled_path', side_effect=lambda name: package / name), patch('installer.install_root', return_value=destination), patch('installer.create_shortcut') as shortcut:
            with self.assertRaises(FileNotFoundError):
                installer.install_taskflow()
        self.assertEqual((destination / 'TaskFlow.exe').read_bytes(), b'existing-app')
        shortcut.assert_not_called()

    def test_prompt_carries_explicit_scope_and_safe_arguments(self):
        self.bind()
        prompt = agent_prompt(self.manager, 'Demo')
        self.assertIn(self.manager.db_file, prompt)
        self.assertIn('--status pending', prompt)
        self.assertIn('needs_review', prompt)
        self.assertIn('--token', prompt)

    def test_gui_observes_external_report_without_size_or_input_changes(self):
        from PyQt5.QtWidgets import QApplication
        from app_gui import TaskFlowApp
        app = QApplication.instance() or QApplication([])
        task = self.manager.add_task('Demo GUI', 'Demo')
        win = TaskFlowApp(start_minimized=True, task_manager=self.manager, setup_autostart=False)
        try:
            win.task_input.setText('Unsaved typing')
            agent = TaskManager(self.json)
            claim = agent.claim_task('Demo', task['id'], 1, 'session')
            agent.report_task('Demo', task['id'], claim['revision'], claim['claim_token'], 'needs_review', 'Visual change', 'offscreen check')
            win._poll_external_changes()
            card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))
            self.assertEqual(card.date_label.text(), 'Kontrolünü bekliyor')
            self.assertFalse(card.checkbox.isChecked())
            self.assertEqual(win.task_input.text(), 'Unsaved typing')
            self.assertEqual((win.width(), win.height()), (440, 640))
        finally:
            win.tray_icon.hide()
            win.sync_timer.stop()
            win.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
