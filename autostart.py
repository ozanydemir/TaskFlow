import sys
import os
import winreg

APP_NAME = 'FlowListTodoList'
REG_PATH = r'Software\Microsoft\Windows\CurrentVersion\Run'

def get_app_command():
    if getattr(sys, 'frozen', False):
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}" --minimized'
    else:
        python_exe = os.path.abspath(sys.executable)
        pythonw = os.path.join(os.path.dirname(python_exe), 'pythonw.exe')
        if os.path.exists(pythonw):
            python_exe = pythonw
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(script_dir, 'main.py')
        return f'"{python_exe}" "{main_script}" --minimized'

def is_autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Error reading autostart registry: {e}")
        return False

def set_autostart(enable=True):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = get_app_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                return True
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                return False
    except Exception as e:
        print(f"Error modifying autostart registry: {e}")
        return False

def toggle_autostart():
    current = is_autostart_enabled()
    new_state = not current
    set_autostart(new_state)
    return new_state