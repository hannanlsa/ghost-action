#!/usr/bin/env python3
import PyInstaller.__main__
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

args = [
    os.path.join(ROOT, "main.py"),
    "--name=GhostAction",
    "--windowed",
    "--onedir",
    "--noconfirm",
    f"--add-data={SRC}{os.pathsep}src",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=pytesseract",
    "--hidden-import=cv2",
    "--hidden-import=mss",
    "--hidden-import=Quartz",
    "--hidden-import=objc",
    "--hidden-import=marketplace",
    "--hidden-import=data_source",
    "--hidden-import=ai_recognizer",
    "--hidden-import=accessibility",
    "--hidden-import=script_manager",
    "--hidden-import=requests",
    "--hidden-import=openpyxl",
    f"--distpath={os.path.join(ROOT, 'dist')}",
    f"--workpath={os.path.join(ROOT, 'build')}",
    f"--specpath={ROOT}",
    "--osx-bundle-identifier=com.ghost-action.app",
]

icon_path = os.path.join(ROOT, "assets", "GhostAction.icns")
if os.path.exists(icon_path):
    args.append(f"--icon={icon_path}")

PyInstaller.__main__.run(args)