"""Render synthetic design fixtures without touching real tasks or autostart."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import sys
import tempfile
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase, QFont
from app_gui import TaskFlowApp
from task_manager import TaskManager


def render():
    app = QApplication.instance() or QApplication(sys.argv)
    # Qt's Windows offscreen plugin does not discover system fonts automatically.
    for font in ['segoeui.ttf', 'segoeuib.ttf', 'segoeuis.ttf', 'segoepr.ttf']:
        font_file = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font
        if font_file.exists():
            QFontDatabase.addApplicationFont(str(font_file))
    app.setFont(QFont('Segoe UI', 10))
    output = Path(__file__).resolve().parent / 'design_mockups'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        manager = TaskManager(Path(directory) / 'data.json')
        # Public preview data only. Never render the developer's real projects
        # or task text into screenshots committed to the repository.
        manager.projects = ['Website Launch', 'Weekly Planning', 'Product Ideas', 'Home Projects']
        done = manager.add_task('Review the launch checklist and confirm the next milestone.', 'Website Launch')
        manager.toggle_task(done['id'])
        manager.add_task('Collect feedback, prioritize the open items, and prepare the next update.', 'Website Launch')
        window = TaskFlowApp(start_minimized=True, task_manager=manager, setup_autostart=False)
        window.show()
        window.task_input.setText('')
        for width, height, name in [(1120, 820, 'taskflow_reference_desktop'), (640, 620, 'taskflow_reference_compact')]:
            window.resize(width, height)
            for _ in range(8):
                app.processEvents()
            window._resize_task_cards()
            app.processEvents()
            window.grab().save(str(output / (name + '.png')))
            print(name, window.size().width(), window.size().height())
            for index in range(window.task_list_widget.count()):
                item = window.task_list_widget.item(index)
                card = window.task_list_widget.itemWidget(item)
                print('card', index, 'height', card.height(), 'title', card.title_label.width(), card.title_label.height())
        manager.tasks = []
        window._refresh_tasks()
        window.resize(1120, 820)
        for _ in range(8):
            app.processEvents()
        window.grab().save(str(output / 'taskflow_reference_empty.png'))
        window.tray_icon.hide()
        window.hide()
        window.deleteLater()
        app.processEvents()


if __name__ == '__main__':
    render()
