"""Shared skill discovery tests use disposable stores and the real source bridge."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from task_manager import TaskManager


@unittest.skipUnless(os.name == 'nt', 'The shared Windows skill uses PowerShell.')
class TestTaskFlowSkill(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tools = self.root / 'tools with spaces'
        self.tools.mkdir()
        self.repo = self.root / 'demo repo'
        self.repo.mkdir()
        (self.repo / '.git').mkdir()
        self.nested = self.repo / 'src'
        self.nested.mkdir()
        self.appdata = self.root / 'profile'
        self.store = self.appdata / 'TaskFlow' / 'data.sqlite3'
        self.manager = TaskManager(self.store)
        self.manager.add_project('Demo Örnek')
        self.manager.bind_project('Demo Örnek', self.repo)
        self.task = self.manager.add_task('Synthetic task', 'Demo Örnek')
        # A test-only PowerShell shim invokes the real bridge with this interpreter.
        self.agent = self.tools / 'test-agent.ps1'
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        bridge = Path(__file__).with_name('taskflow_agent.py')
        self.agent.write_text(f"& {quote(sys.executable)} {quote(bridge)} @args\nexit $LASTEXITCODE\n", encoding='utf-8')
        self.resolver = Path(__file__).parent / 'skills/taskflow/scripts/resolve-taskflow.ps1'
        self.env = dict(os.environ, APPDATA=str(self.appdata), LOCALAPPDATA=str(self.root / 'local'))
        self.original_tasks = self.manager.tasks.copy()

    def tearDown(self):
        self.temp.cleanup()

    def resolve(self, *args):
        return subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(self.resolver), '-AgentPath', str(self.agent), *map(str, args)],
            capture_output=True, encoding='utf-8', env=self.env, timeout=30)

    def assert_error(self, result, text):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(text, result.stderr)

    def test_named_project_case_insensitive_preserves_exact_name_and_tasks(self):
        result = self.resolve('-Project', 'demo örnek')
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(context['project'], 'Demo Örnek')
        self.assertTrue(Path(context['database']).samefile(self.store))
        self.assertTrue(Path(context['repo_path']).samefile(self.repo))
        self.assertEqual(TaskManager(self.store).tasks, self.original_tasks)

    def test_current_repository_is_inferred_from_a_nested_directory(self):
        result = self.resolve('-Repo', self.nested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['project'], 'Demo Örnek')

    def test_unknown_project_does_not_match_a_prefix(self):
        self.assert_error(self.resolve('-Project', 'Demo'), 'No unique')
        self.assertEqual(TaskManager(self.store).tasks, self.original_tasks)

    def test_unbound_project_reports_connection_setup(self):
        self.manager.add_project('Unbound')
        self.assert_error(self.resolve('-Project', 'Unbound'), 'no agent connection')

    def test_missing_database_is_not_created(self):
        absent = self.root / 'absent.sqlite3'
        self.assert_error(self.resolve('-Project', 'Demo Örnek', '-Database', absent), 'database is missing')
        self.assertFalse(absent.exists())
        self.assertFalse(absent.with_suffix('.json').exists())

    def test_invalid_database_is_not_changed(self):
        invalid = self.root / 'invalid.sqlite3'
        invalid.write_bytes(b'not a database')
        self.assert_error(self.resolve('-Project', 'Demo Örnek', '-Database', invalid), 'not a SQLite')
        self.assertEqual(invalid.read_bytes(), b'not a database')

    def test_portable_store_takes_priority_over_appdata(self):
        portable = TaskManager(self.tools / 'data.sqlite3')
        portable.add_project('Portable')
        portable.bind_project('Portable', self.repo)
        result = self.resolve('-Project', 'Portable')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)['database']).samefile(self.tools / 'data.sqlite3'))
        self.assertEqual(TaskManager(self.store).tasks, self.original_tasks)

    def test_unmigrated_portable_json_does_not_silently_use_another_store(self):
        source = self.tools / 'data.json'
        source.write_text('{"projects":["Portable"]}', encoding='utf-8')
        self.assert_error(self.resolve('-Project', 'Demo Örnek'), 'has not been migrated')
        self.assertFalse(source.with_suffix('.sqlite3').exists())

    def test_missing_saved_repository_is_refused(self):
        (self.repo / '.git').rmdir()
        self.assert_error(self.resolve('-Project', 'Demo Örnek'), 'not a Git root')
        self.assertEqual(TaskManager(self.store).tasks, self.original_tasks)

    def test_resolved_context_drives_real_bridge_round_trip(self):
        resolved = self.resolve('-Repo', self.repo)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        context = json.loads(resolved.stdout)
        base = [sys.executable, str(Path(__file__).with_name('taskflow_agent.py')),
                '--db', context['database']]
        def bridge(*args):
            output = subprocess.run(base + list(args), capture_output=True, encoding='utf-8', timeout=30)
            self.assertEqual(output.returncode, 0, output.stderr)
            return json.loads(output.stdout)['result']
        task = bridge('list', '--project', context['project'], '--status', 'pending')['tasks'][0]
        claim = bridge('claim', '--project', context['project'], '--repo', context['repo_path'],
                       '--id', task['id'], '--revision', str(task['revision']), '--owner', 'skill-test')
        report = bridge('report', '--project', context['project'], '--repo', context['repo_path'],
                        '--id', claim['id'], '--revision', str(claim['revision']),
                        '--token', claim['claim_token'], '--status', 'completed',
                        '--summary', 'Synthetic round trip', '--evidence', 'Bridge round-trip assertions passed')
        self.assertEqual(report['status'], 'completed')
        self.assertTrue(TaskManager(self.store).tasks[0]['completed'])


if __name__ == '__main__':
    unittest.main()
