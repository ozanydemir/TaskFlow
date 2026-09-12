import os
import subprocess
import sys
import shutil

def build():
    print("Starting FlowList EXE build...")
    
    # Ensure resources exist
    if not os.path.exists("resources/icon.ico") or not os.path.exists("resources/icon.png"):
        print("Resources not found! Generating icons...")
        import generate_icon

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        "--name=FlowList",
        "--icon=resources/icon.ico",
        "--add-data=resources;resources",
        "main.py"
    ]
    
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = os.path.abspath("dist/FlowList.exe")
        print("\n========================================")
        print("BUILD SUCCESSFUL!")
        print(f"Executable location: {exe_path}")
        print(f"File size: {os.path.getsize(exe_path) / (1024*1024):.2f} MB")
        print("========================================\n")
    else:
        print("Build failed with return code", result.returncode)

if __name__ == "__main__":
    build()