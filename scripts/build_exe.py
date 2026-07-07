#!/usr/bin/env python3
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

subprocess.run([
    "pyinstaller",
    "--name", "GhostAction",
    "--onefile",
    "--windowed",
    "--add-data", f"{os.path.join(ROOT, 'src')}{os.pathsep}src",
    os.path.join(ROOT, "main.py"),
], cwd=ROOT, check=True)

print("EXE built: dist/GhostAction.exe")