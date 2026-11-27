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
        self.directory = tempfile.TemporaryDirectory()
        self.test_file = str(Path(self.directory.name) / 'data.json')
        self.tm = TaskManager(self.test_file)

    def tearDown(self):
        self.directory.cleanup()

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
        self.assertFalse(any(t['id'] == t1['id'] for t in self.tm.get_tasks()))
        self.assertTrue(any(t['id'] == t1['id'] for t in self.tm.get_tasks(archived=True)))

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

    def test_task_menu_click_over_window_edge_is_not_a_resize(self):
        from PyQt5.QtCore import QTimer
        from PyQt5.QtTest import QTest
        from PyQt5.QtWidgets import QMenu
        from app_gui import TaskFlowApp
        task = self.tm.add_task('Silinecek görev')
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        clicked = []
        try:
            win.move(40, 20)
            win.show()
            self.app.processEvents()
            card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))

            def click_delete_inside_edge_band():
                menu = QApplication.activePopupWidget()
                self.assertIsInstance(menu, QMenu)
                # Real screens open the menu across the window's right resize catchment.
                menu.move(win.mapToGlobal(QPoint(win.width() - 60, 200)))
                self.app.processEvents()
                action = next(a for a in menu.actions() if a.text() == 'Görevi sil')
                row = menu.actionGeometry(action)
                x = menu.mapFromGlobal(win.mapToGlobal(QPoint(win.width() - 8, 0))).x()
                self.assertTrue(row.left() <= x <= row.right())
                QTest.mouseClick(menu, Qt.LeftButton, Qt.NoModifier, QPoint(x, row.center().y()))
                clicked.append(menu.isVisible())
                menu.close()

            QTimer.singleShot(0, click_delete_inside_edge_band)
            card.menu_btn.click()
            self.assertEqual(clicked, [False])
            self.assertFalse(any(t['id'] == task['id'] for t in TaskManager(self.test_file).tasks))
            self.assertIsNone(win._resizing_edge)

            # The catchment still works over the main window's own children.
            viewport = win.task_list_widget.viewport()
            edge = viewport.mapFromGlobal(win.mapToGlobal(QPoint(win.width() - 4, 300)))
            QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, edge)
            self.assertEqual(win._resizing_edge, (False, True, False, False))
            QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, edge)
            self.assertIsNone(win._resizing_edge)
        finally:
            win.tray_icon.hide()
            win.hide()
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

    def test_p0_external_poll_defers_while_modal_dialog_is_open(self):
        from PyQt5.QtCore import QTimer
        from app_gui import CustomInputDialog, TaskFlowApp
        task = self.tm.add_task('Düzenlenen görev', 'Demo')
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        try:
            win.show()
            self.app.processEvents()
            original_card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))
            dialog = CustomInputDialog('Görevi Düzenle', 'Metin:', win, confirm_text='Kaydet')
            state = {}

            def mutate_during_modal():
                TaskManager(self.test_file).add_task('Dışarıdan gelen görev', 'Demo')
                win._poll_external_changes()
                state['deferred'] = win._pending_external_refresh
                state['same_card'] = win.task_list_widget.itemWidget(win.task_list_widget.item(0)) is original_card
                dialog.accept()

            QTimer.singleShot(0, mutate_during_modal)
            dialog.exec_()
            self.assertTrue(state.get('deferred'))
            self.assertTrue(state.get('same_card'))
            win._poll_external_changes()
            self.assertFalse(win._pending_external_refresh)
            self.assertEqual(win.task_list_widget.count(), 2)
        finally:
            win.sync_timer.stop()
            win.tray_icon.hide()
            win.hide()
            win.deleteLater()
            self.app.processEvents()

    def test_p0_outward_resize_and_outside_release_do_not_stick(self):
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtCore import QEvent, QPointF
        from app_gui import TaskFlowApp
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        try:
            win.move(100, 100)
            win.show()
            self.app.processEvents()
            start_w = win.width()
            edge_local = QPoint(win.width() - 4, 200)
            press = QMouseEvent(QEvent.MouseButtonPress, QPointF(edge_local), QPointF(win.mapToGlobal(edge_local)),
                                Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            self.assertTrue(win.eventFilter(win, press))
            self.assertEqual(win._resizing_edge, (False, True, False, False))

            # Move pointer outside self.rect() to enlarge the window
            outside_local = QPoint(win.width() + 50, 200)
            move = QMouseEvent(QEvent.MouseMove, QPointF(outside_local), QPointF(win.mapToGlobal(outside_local)),
                               Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
            self.assertTrue(win.eventFilter(win, move))
            self.assertGreater(win.width(), start_w)

            # Release outside self.rect() must clear _resizing_edge
            rel_local = QPoint(win.width() + 80, 200)
            release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(rel_local), QPointF(win.mapToGlobal(rel_local)),
                                  Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
            self.assertTrue(win.eventFilter(win, release))
            self.assertIsNone(win._resizing_edge)
        finally:
            win.sync_timer.stop()
            win.tray_icon.hide()
            win.hide()
            win.deleteLater()
            self.app.processEvents()

    def test_p0_scroll_position_and_far_tab_visibility_preserved(self):
        from app_gui import TaskFlowApp
        for i in range(1, 10):
            self.tm.add_project(f'Project-{i}-LongTab')
        for i in range(15):
            self.tm.add_task(f'Uzun görev satırı {i}', 'Project-1-LongTab')
        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        try:
            win.show()
            for _ in range(5):
                self.app.processEvents()
            win._resize_task_cards()
            self.app.processEvents()

            bar = win.task_list_widget.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            target_scroll = bar.maximum()
            bar.setValue(target_scroll)
            task_id = self.tm.tasks[5]['id']
            win._on_task_edited(task_id, 'Güncellenmiş görev')
            for _ in range(4):
                self.app.processEvents()
            self.assertGreater(win.task_list_widget.verticalScrollBar().value(), 0)

            win._select_project('Project-9-LongTab')
            for _ in range(5):
                self.app.processEvents()
            btn = win._tab_buttons['Project-9-LongTab']
            sv = win.tabs_scroll.horizontalScrollBar().value()
            vw = win.tabs_scroll.viewport().width()
            self.assertGreaterEqual(btn.x() + btn.width(), sv)
            self.assertLessEqual(btn.x(), sv + vw)
        finally:
            win.sync_timer.stop()
            win.tray_icon.hide()
            win.hide()
            win.deleteLater()
            self.app.processEvents()

    def test_p1_escape_undo_move_rename_unbind_and_compact_layout(self):
        from PyQt5.QtTest import QTest
        from app_gui import CustomConfirmDialog, CustomInputDialog, TaskFlowApp
        repo = Path(self.directory.name) / 'repo'
        (repo / '.git').mkdir(parents=True)
        brain = Path(self.directory.name) / 'brain'
        brain.mkdir()
        (brain / 'PROJECT_CONTEXT.md').write_text('# Demo', encoding='utf-8')
        self.tm.add_project('Alpha')
        self.tm.add_project('Beta')
        self.tm.bind_project('Alpha', repo, brain)
        t_loose = self.tm.add_task('Projesiz görev')
        t_note = self.tm.add_task('Notlu görev', 'Alpha')
        self.tm.edit_notes(t_note['id'], 'Kısa not 440px görünür olmalı')
        t_done = self.tm.add_task('Tamamlanan görev', 'Alpha')
        self.tm.toggle_task(t_done['id'])

        # Move task to project
        self.tm.move_task_project(t_loose['id'], 'Beta')
        self.assertEqual(next(t for t in self.tm.tasks if t['id'] == t_loose['id'])['project'], 'Beta')

        # Rename project keeps project_id, tasks, and history
        old_uid = self.tm.project_ids['Alpha']
        self.assertTrue(self.tm.rename_project('Alpha', 'AlphaRenamed'))
        self.assertEqual(self.tm.project_ids['AlphaRenamed'], old_uid)
        self.assertEqual(next(t for t in self.tm.tasks if t['id'] == t_note['id'])['project'], 'AlphaRenamed')
        self.assertTrue(len(self.tm.get_history('AlphaRenamed')) >= 1)

        # Unbind project detaches TODO projection cleanly
        self.assertTrue(self.tm.unbind_project('AlphaRenamed'))
        self.assertNotIn('AlphaRenamed', self.tm.bindings)
        self.assertNotIn('taskflow:begin', (brain / 'TODO.md').read_text(encoding='utf-8'))

        win = TaskFlowApp(start_minimized=True, task_manager=self.tm, setup_autostart=False)
        try:
            win.show()
            for _ in range(5):
                self.app.processEvents()
            win._resize_task_cards()
            self.app.processEvents()

            # Active tasks sorted above completed tasks
            first_card = win.task_list_widget.itemWidget(win.task_list_widget.item(0))
            last_card = win.task_list_widget.itemWidget(win.task_list_widget.item(win.task_list_widget.count() - 1))
            self.assertFalse(first_card.task.get('completed'))
            self.assertTrue(last_card.task.get('completed'))

            # Notes visible at default 440px width
            note_card = next(
                win.task_list_widget.itemWidget(win.task_list_widget.item(i))
                for i in range(win.task_list_widget.count())
                if win.task_list_widget.itemWidget(win.task_list_widget.item(i)).task['id'] == t_note['id']
            )
            self.assertTrue(note_card.note_btn.isVisible())

            # Escape clears focused task_input without hiding window
            win.task_input.setFocus()
            win.task_input.setText('Taslak')
            QTest.keyClick(win.task_input, Qt.Key_Escape)
            self.assertTrue(win.isVisible())
            self.assertEqual(win.task_input.text(), '')

            # Delete shows Undo bar and Undo restores task
            win._on_task_deleted(t_loose['id'])
            self.assertTrue(win.undo_bar.isVisible())
            self.assertFalse(any(t['id'] == t_loose['id'] for t in win.task_manager.tasks))
            win._undo_last_action()
            self.assertFalse(win.undo_bar.isVisible())
            self.assertTrue(any(t['id'] == t_loose['id'] for t in win.task_manager.tasks))

            # 400px & 340px layout checks: no clipping
            win.resize(400, 640)
            for _ in range(4):
                self.app.processEvents()
            self.assertEqual(win.clear_btn.text(), 'Arşivle')
            self.assertGreaterEqual(win.footer.width(), win.footer.minimumSizeHint().width())

            win.resize(340, 460)
            for _ in range(4):
                self.app.processEvents()
            self.assertFalse(win.subtitle_lbl.isVisible())
            self.assertGreaterEqual(win.title_lbl.width(), win.title_lbl.sizeHint().width())
            self.assertGreaterEqual(win.stats_lbl.width(), win.stats_lbl.sizeHint().width())
            self.assertGreaterEqual(win.footer.width(), win.footer.minimumSizeHint().width())

            # Dialog contracts
            d_edit = CustomInputDialog('Düzenle', 'Metin:', win, confirm_text='Kaydet', multiline=True)
            d_edit.set_text('Satır 1\nSatır 2')
            self.assertEqual(d_edit.ok_btn.text(), 'Kaydet')
            self.assertEqual(d_edit.get_text(), 'Satır 1\nSatır 2')
            d_edit.deleteLater()

            d_info = CustomConfirmDialog('Bilgi', 'Mesaj', confirm_text='Tamam', is_destructive=False,
                                         parent=win, show_cancel=False)
            self.assertIsNone(d_info.cancel_btn)
            d_info.deleteLater()
        finally:
            win.sync_timer.stop()
            win.tray_icon.hide()
            win.hide()
            win.deleteLater()
            self.app.processEvents()

if __name__ == '__main__':
    unittest.main()
