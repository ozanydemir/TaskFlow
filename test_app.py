import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QFontDatabase, QFontMetrics

from task_manager import TaskManager
import autostart

class TestTaskFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        for font in ['segoeui.ttf', 'segoeuib.ttf', 'segoeuis.ttf', 'segoepr.ttf']:
            font_file = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font
            if font_file.exists():
                QFontDatabase.addApplicationFont(str(font_file))
        cls.app.setFont(QFont('Segoe UI', 10))

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
        from app_gui import TaskFlowApp
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        self.assertIsNotNone(win)
        self.assertIsNotNone(win.tray_icon)

        # Test adding task via GUI logic
        win.task_input.setText("GUI Test Task")
        win._add_task()
        self.assertTrue(any(t['title'] == "GUI Test Task" for t in win.task_manager.tasks))

        win.hide_to_tray()
        self.assertFalse(win.isVisible())
        win.tray_icon.hide()
        win.deleteLater()
        app.processEvents()

    def test_notes_and_completion_date_survive_reload(self):
        task = self.tm.add_task('Kalıcı görev', 'Proje')
        self.assertTrue(self.tm.edit_notes(task['id'], '  Görüşme notu  '))
        self.tm.toggle_task(task['id'])
        restored = TaskManager(self.test_file).tasks[0]
        self.assertEqual(restored['notes'], 'Görüşme notu')
        self.assertTrue(restored['completed'])
        self.assertIn('completed_at', restored)
        self.tm.toggle_task(task['id'])
        self.assertNotIn('completed_at', TaskManager(self.test_file).tasks[0])

    def test_legacy_data_copy_keeps_original_and_new_data_wins(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'APPDATA': directory}):
            legacy = Path(directory) / 'FlowList' / 'data.json'
            legacy.parent.mkdir()
            original = json.dumps({'projects': ['Eski Proje'], 'tasks': [{'id': 'legacy', 'title': 'Eski görev'}], 'settings': {'always_on_top': True}}, ensure_ascii=False).encode('utf-8')
            legacy.write_bytes(original)
            migrated = TaskManager()
            self.assertEqual(Path(migrated.data_file).parent.name, 'TaskFlow')
            self.assertEqual(migrated.tasks[0]['id'], 'legacy')
            self.assertTrue(migrated.settings['always_on_top'])
            self.assertEqual(legacy.read_bytes(), original)
            migrated.add_task('Yeni görev')
            self.assertEqual(TaskManager().tasks[0]['title'], 'Yeni görev')
            self.assertEqual(legacy.read_bytes(), original)

    def test_gui_pin_hide_close_and_filter_preserve_behavior(self):
        from app_gui import TaskFlowApp
        self.tm.add_task('Birinci', 'A')
        self.tm.add_task('İkinci', 'B')
        with patch('autostart.set_autostart') as startup:
            win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
            startup.assert_not_called()
        try:
            self.assertEqual((win.width(), win.height()), (440, 640))
            self.assertEqual(win._get_resize_edge(QPoint(12, 300)), (True, False, False, False))
            self.assertEqual(win._get_resize_edge(QPoint(1, 1)), (True, False, True, False))
            self.assertEqual(win._get_resize_edge(QPoint(win.width() - 1, win.height() - 1)), (False, True, False, True))
            win._select_project('A')
            self.assertEqual(win.task_list_widget.count(), 1)
            win.show()
            win.pin_btn.click()
            self.assertTrue(win.windowFlags() & Qt.WindowStaysOnTopHint)
            self.assertTrue(TaskManager(self.test_file).settings['always_on_top'])
            win.pin_btn.click()
            self.assertFalse(win.windowFlags() & Qt.WindowStaysOnTopHint)
            win.hide_btn.click()
            self.assertFalse(win.isVisible())
            win.toggle_window_visibility()
            self.assertTrue(win.isVisible())
            win.close_btn.click()
            self.assertFalse(win.isVisible())
        finally:
            win.tray_icon.hide()
            win.deleteLater()
            self.app.processEvents()

    def test_long_task_and_project_fit_after_window_resize(self):
        from app_gui import TaskFlowApp
        project = 'Uzun proje adı ' * 12
        self.tm.add_task('Uzun görev açıklaması ve kontrol edilecek ayrıntılar. ' * 8, project)
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        try:
            win.show()
            for width in (1120, 640):
                win.resize(width, 820 if width == 1120 else 620)
                for _ in range(8):
                    self.app.processEvents()
                win._resize_task_cards()
                self.app.processEvents()
                card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))
                label = card.title_label
                needed = QFontMetrics(label.font()).boundingRect(0, 0, label.width(), 10000, Qt.TextWordWrap, label.text()).height()
                self.assertGreaterEqual(label.height(), needed)
                self.assertLessEqual(card.badge.geometry().right(), card.width())
                self.assertLessEqual(card.badge.geometry().bottom(), card.height())
                self.assertLessEqual(card.menu_btn.geometry().right(), card.width())
        finally:
            win.tray_icon.hide()
            win.hide()
            win.deleteLater()
            self.app.processEvents()

if __name__ == '__main__':
    unittest.main()
