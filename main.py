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

def main():
    _log_debug("=== TaskFlow starting up ===")
    try:
        # Parse CLI args
        parser = argparse.ArgumentParser(description="TaskFlow Desktop To-Do App")
        parser.add_argument('--minimized', action='store_true', help="Start minimized in system tray")
        args, _ = parser.parse_known_args()

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