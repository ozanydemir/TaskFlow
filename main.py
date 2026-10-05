import os
import sys
import argparse
import ctypes
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from app_gui import TaskFlowApp

def _log_debug(msg):
    try:
        log_dir = os.path.join(os.environ.get('APPDATA', '.'), 'TaskFlow')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'startup_debug.log'), 'a', encoding='utf-8') as f:
            f.write(f"{msg}\n")
    except Exception:
        pass

def _verify_build(report_file):
    """Exercise the frozen GUI with disposable data, never the user's configuration."""
    import json
    import tempfile
    from pathlib import Path
    from task_manager import TaskManager
    app = QApplication(['TaskFlow verification'])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory() as directory:
        manager = TaskManager(Path(directory) / 'data.json')
        manager.settings['autostart'] = False
        manager.save()
        task = manager.add_task('Synthetic package task', 'Demo')
        window = TaskFlowApp(start_minimized=True, task_manager=manager, setup_autostart=False)
        external = TaskManager(manager.db_file)
        claim = external.claim_task('Demo', task['id'], task['revision'], 'build-verification')
        external.report_task('Demo', task['id'], claim['revision'], claim['claim_token'],
                             'completed', 'Synthetic verification', 'Packaged GUI and SQLite round trip passed')
        window._poll_external_changes()
        app.processEvents()
        card = window.task_list_widget.itemWidget(window.task_list_widget.item(0))
        assert card.checkbox.isChecked()
        assert card.date_label.text().startswith('Yerelde tamamlandı')
        completed = external.get_tasks('Demo')[0]
        published = external.mark_published('Demo', task['id'], completed['revision'], 'Synthetic deployment check')
        external.archive_completed('Demo')
        window._poll_external_changes()
        assert window.task_list_widget.count() == 0
        from app_gui import TaskArchiveDialog
        archive = TaskArchiveDialog(manager, 'Demo', window)
        assert archive.list.count() == 1
        assert 'Synthetic verification' in archive.details.toPlainText()
        archive._restore()
        window._refresh_tasks()
        assert window.task_list_widget.count() == 1
        assert manager.get_tasks('Demo')[0]['delivery'] == 'published'
        assert len(manager.get_history('Demo')) == 4
        archive.deleteLater()
        assert (window.width(), window.height()) == (440, 640)
        assert Path(getattr(sys, '_MEIPASS', Path(__file__).parent), 'resources', 'icon.ico').is_file()
        window.sync_timer.stop()
        window.tray_icon.hide()
        window.deleteLater()
        app.processEvents()
    Path(report_file).write_text(json.dumps({'ok': True, 'checks': ['frozen GUI', 'SQLite', 'external result refresh',
                                                                  'compact dimensions', 'bundled icon', 'delivery state',
                                                                  'archive and restore', 'persistent journal']}), encoding='utf-8')


def main():
    _log_debug("=== TaskFlow starting up ===")
    try:
        # Parse CLI args
        parser = argparse.ArgumentParser(description="TaskFlow Desktop To-Do App")
        parser.add_argument('--minimized', action='store_true', help="Start minimized in system tray")
        parser.add_argument('--verify-build', help=argparse.SUPPRESS)
        args, _ = parser.parse_known_args()
        if args.verify_build:
            _verify_build(args.verify_build)
            return

        # Set Windows App ID for proper taskbar icon handling
        try:
            myappid = 'taskflow.todolist.desktop.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            _log_debug(f"AppUserModelID warning: {e}")

        # High DPI Scaling
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # Windows Single Instance check using Mutex
        mutex = None
        try:
            import win32event
            import win32api
            import winerror
            mutex = win32event.CreateMutex(None, False, "FlowList_SingleInstance_Mutex_82736")
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                _log_debug("Another instance already running. Exiting.")
                sys.exit(0)
        except Exception as e:
            _log_debug(f"Mutex warning: {e}")

        app = QApplication(sys.argv)
        app.setApplicationName("TaskFlow")
        app.setQuitOnLastWindowClosed(False)

        window = TaskFlowApp(start_minimized=args.minimized)
        _log_debug("Window initialized and entering event loop.")
        exit_code = app.exec_()
        _log_debug(f"App exited with code: {exit_code}")

        if mutex:
            try:
                import win32api
                win32api.CloseHandle(mutex)
            except Exception:
                pass

        sys.exit(exit_code)
    except Exception as e:
        import traceback
        _log_debug(f"FATAL ERROR:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main()