import os
import sys
import argparse
import ctypes
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from app_gui import FlowListApp

def main():
    # Parse CLI args
    parser = argparse.ArgumentParser(description="FlowList Desktop To-Do App")
    parser.add_argument('--minimized', action='store_true', help="Start minimized in system tray")
    args, _ = parser.parse_known_args()

    # Set Windows App ID for proper taskbar icon handling
    try:
        myappid = 'flowlist.todolist.desktop.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

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
            print("FlowList is already running in background/tray.")
            sys.exit(0)
    except Exception as e:
        # Fallback if win32event not available
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray when window is hidden!

    window = FlowListApp(start_minimized=args.minimized)
    exit_code = app.exec_()

    # Release mutex if held
    if mutex:
        try:
            import win32api
            win32api.CloseHandle(mutex)
        except Exception:
            pass

    sys.exit(exit_code)

if __name__ == '__main__':
    main()