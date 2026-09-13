import os
import subprocess
import sys
import shutil
import argparse

def build(dist_dir='dist'):
    print("Starting TaskFlow EXE build...")
    
    # Ensure resources exist
    if not os.path.exists("resources/icon.ico") or not os.path.exists("resources/icon.png") or not os.path.exists("resources/app_logo.png"):
        print("Resources not found! Generating icons...")
        import generate_icon
        generate_icon.generate_icons()

    if os.path.exists("TaskFlow.spec"):
        # The local spec can reuse the previous runtime DLL to keep the
        # package footprint stable. A clean checkout falls back to the
        # standard PyInstaller command below.
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", f"--distpath={dist_dir}", "TaskFlow.spec"]
    else:
        cmd = [
            sys.executable, "-m", "PyInstaller", "--noconsole", "--onefile", "--clean",
            f"--name=TaskFlow", f"--distpath={dist_dir}", "--icon=resources/icon.ico",
            "--add-data=resources;resources", "main.py"
        ]
    
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = os.path.abspath(os.path.join(dist_dir, "TaskFlow.exe"))
        print("\n========================================")
        print("BUILD SUCCESSFUL!")
        print(f"Executable location: {exe_path}")
        print(f"File size: {os.path.getsize(exe_path) / (1024*1024):.2f} MB")
        print("========================================\n")
    else:
        print("Build failed with return code", result.returncode)
        raise SystemExit(result.returncode)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build TaskFlow for Windows')
    parser.add_argument('--dist-dir', default='dist', help='Output folder, e.g. dist_next when the app is running')
    build(parser.parse_args().dist_dir)
