import os
import sys
import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from task_manager import TaskManager
import autostart

class TestFlowList(unittest.TestCase):
    def setUp(self):
        self.test_file = os.path.abspath('test_run_data.json')
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        self.tm = TaskManager(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_task_operations(self):
        # 1. Add Task
        t1 = self.tm.add_task("Gorev 1", "İş")
        self.assertIsNotNone(t1)
        self.assertEqual(t1['title'], "Gorev 1")
        self.assertEqual(t1['project'], "İş")

        t2 = self.tm.add_task("Gorev 2", "Kişisel")
        self.assertIsNotNone(t2)

        # 2. Filter tasks
        is_tasks = self.tm.get_tasks("İş")
        self.assertTrue(any(t['title'] == "Gorev 1" for t in is_tasks))

        # 3. Toggle task
        self.tm.toggle_task(t1['id'])
        updated_t1 = next(t for t in self.tm.tasks if t['id'] == t1['id'])
        self.assertTrue(updated_t1['completed'])

        # 4. Edit task
        self.tm.edit_task(t1['id'], "Gorev 1 Guncellendi")
        updated_t1 = next(t for t in self.tm.tasks if t['id'] == t1['id'])
        self.assertEqual(updated_t1['title'], "Gorev 1 Guncellendi")

        # 5. Stats
        total, completed = self.tm.get_stats("Tümü")
        self.assertGreaterEqual(total, 2)
        self.assertGreaterEqual(completed, 1)

        # 6. Clear completed
        self.tm.clear_completed("Tümü")
        self.assertFalse(any(t['id'] == t1['id'] for t in self.tm.tasks))

    def test_project_operations(self):
        self.tm.add_project("YeniProje123")
        self.assertIn("YeniProje123", self.tm.projects)
        self.tm.delete_project("YeniProje123")
        self.assertNotIn("YeniProje123", self.tm.projects)

    def test_autostart_query(self):
        # Read status should not crash
        status = autostart.is_autostart_enabled()
        self.assertIsInstance(status, bool)

    def test_gui_initialization(self):
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        from app_gui import FlowListApp
        win = FlowListApp(start_minimized=True)
        self.assertIsNotNone(win)
        self.assertIsNotNone(win.tray_icon)

        # Test adding task via GUI logic
        win.task_input.setText("GUI Test Task")
        win._add_task()
        self.assertTrue(any(t['title'] == "GUI Test Task" for t in win.task_manager.tasks))

        win.hide_to_tray()
        self.assertFalse(win.isVisible())
        win.close()

if __name__ == '__main__':
    unittest.main()