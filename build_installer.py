"""Build the downloadable TaskFlowSetup.exe wizard."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build(output_dir: str = "dist_installer") -> Path:
    payload = ROOT / "dist" / "TaskFlow.exe"
    if not payload.is_file():
        raise FileNotFoundError("dist/TaskFlow.exe bulunamadı. Önce python build_exe.py çalıştırın.")

    destination = ROOT / output_dir
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconsole",
        "--onefile",
        f"--name=TaskFlowSetup",
        f"--distpath={destination}",
        "--icon=resources/icon.ico",
        f"--add-binary={payload};payload",
        "--hidden-import=win32com.client",
        "--hidden-import=pythoncom",
        "--hidden-import=pywintypes",
        "installer.py",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return destination / "TaskFlowSetup.exe"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="dist_installer")
    args = parser.parse_args()
    result = build(args.output_dir)
    print(f"Installer hazır: {result} ({result.stat().st_size:,} bytes)")
