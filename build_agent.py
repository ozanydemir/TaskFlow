"""Build the small console bridge independently of the Qt desktop package."""
import subprocess
import sys
from pathlib import Path


def build():
    root = Path(__file__).resolve().parent
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--onefile', '--console',
                    '--name=TaskFlowAgent', '--distpath=dist_agent', '--workpath=build/agent',
                    '--specpath=build', 'taskflow_agent.py'], cwd=root, check=True)
    result = root / 'dist_agent' / 'TaskFlowAgent.exe'
    print(f'Agent bridge ready: {result} ({result.stat().st_size:,} bytes)')
    return result


if __name__ == '__main__':
    build()
