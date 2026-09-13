"""Small self-contained Windows installer for the public TaskFlow release."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk


APP_NAME = "TaskFlow"


def bundled_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def install_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "Programs" / APP_NAME


def create_shortcut(shortcut: Path, target: Path, working_dir: Path) -> None:
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    try:
        import win32com.client  # type: ignore

        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortcut(str(shortcut))
        link.TargetPath = str(target)
        link.WorkingDirectory = str(working_dir)
        link.IconLocation = f"{target},0"
        link.Description = "TaskFlow masaüstü görev takip uygulaması"
        link.Save()
        return
    except Exception:
        # Keep the installer usable on a clean machine without pywin32.
        escaped_shortcut = str(shortcut).replace("'", "''")
        escaped_target = str(target).replace("'", "''")
        escaped_working = str(working_dir).replace("'", "''")
        script = (
            "$ws=New-Object -ComObject WScript.Shell;"
            f"$sc=$ws.CreateShortcut('{escaped_shortcut}');"
            f"$sc.TargetPath='{escaped_target}';"
            f"$sc.WorkingDirectory='{escaped_working}';"
            f"$sc.IconLocation='{escaped_target},0';"
            "$sc.Save()"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def install_taskflow() -> Path:
    payload = bundled_path("payload/TaskFlow.exe")
    if not payload.is_file():
        raise FileNotFoundError("Kurulum paketi içinde TaskFlow.exe bulunamadı.")

    destination = install_root()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "TaskFlow.exe"
    shutil.copy2(payload, target)

    desktop = Path.home() / "Desktop"
    create_shortcut(desktop / "TaskFlow.lnk", target, destination)
    start_menu = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    create_shortcut(start_menu / "TaskFlow.lnk", target, destination)
    return target


class InstallerWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("TaskFlow Kurulumu")
        self.root.geometry("520x300")
        self.root.resizable(False, False)
        self.root.configure(bg="#0b1220")
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TaskFlow.Horizontal.TProgressbar", troughcolor="#17243a", background="#3d82ff")

        body = tk.Frame(self.root, bg="#0b1220", padx=30, pady=24)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="TaskFlow", fg="#f4f7ff", bg="#0b1220", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text="Windows görev takip uygulaması kuruluyor.",
            fg="#a5b9df",
            bg="#0b1220",
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(4, 18))
        tk.Label(body, text="Kurulum konumu", fg="#91a5c7", bg="#0b1220", font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(body, text=str(install_root()), fg="#e5edff", bg="#0b1220", font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 18))
        self.status = tk.Label(body, text="Kurulum hazırlanıyor...", fg="#a5b9df", bg="#0b1220", font=("Segoe UI", 10))
        self.status.pack(anchor="w")
        self.progress = ttk.Progressbar(body, style="TaskFlow.Horizontal.TProgressbar", mode="indeterminate")
        self.progress.pack(fill="x", pady=(10, 0))
        self.root.after(500, self.start_install)

    def start_install(self) -> None:
        self.progress.start(12)
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        try:
            target = install_taskflow()
        except Exception as exc:  # pragma: no cover - exercised by installer users
            self.root.after(0, lambda: self.failed(str(exc)))
            return
        self.root.after(0, lambda: self.finished(target))

    def failed(self, message: str) -> None:
        self.progress.stop()
        self.status.configure(text=f"Kurulum başarısız: {message}", fg="#ff9aa9")

    def finished(self, target: Path) -> None:
        self.progress.stop()
        self.status.configure(text="Kurulum tamamlandı. TaskFlow başlatılıyor...", fg="#9fe3bd")
        self.root.after(700, lambda: self.launch(target))

    def launch(self, target: Path) -> None:
        subprocess.Popen([str(target)], cwd=str(target.parent))
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    InstallerWindow().run()
