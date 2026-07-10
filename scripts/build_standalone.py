#!/usr/bin/env python3
import PyInstaller.__main__
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

CHROMIUM_CACHE = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")

def find_chromium():
    if not os.path.exists(CHROMIUM_CACHE):
        return None
    for d in sorted(os.listdir(CHROMIUM_CACHE), reverse=True):
        if d.startswith("chromium-") and not d.startswith("chromium_headless"):
            full = os.path.join(CHROMIUM_CACHE, d)
            mac_arm = os.path.join(full, "chrome-mac-arm64")
            mac_intel = os.path.join(full, "chrome-mac")
            if os.path.exists(mac_arm):
                return mac_arm
            if os.path.exists(mac_intel):
                return mac_intel
    return None

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
    "--hidden-import=playwright",
    "--hidden-import=playwright.sync_api",
    "--hidden-import=browser_engine",
    "--hidden-import=ui_detector",
    "--hidden-import=onnxruntime",
    f"--distpath={os.path.join(ROOT, 'dist')}",
    f"--workpath={os.path.join(ROOT, 'build')}",
    f"--specpath={ROOT}",
    "--osx-bundle-identifier=com.ghost-action.app",
]

icon_path = os.path.join(ROOT, "assets", "GhostAction.icns")
if os.path.exists(icon_path):
    args.append(f"--icon={icon_path}")

PyInstaller.__main__.run(args)

chromium_src = find_chromium()
if chromium_src:
    dist_chromium = os.path.join(ROOT, "dist", "GhostAction", "chromium")
    if os.path.exists(dist_chromium):
        shutil.rmtree(dist_chromium)
    shutil.copytree(chromium_src, dist_chromium)
    print(f"[build] Chromium copied to dist: {dist_chromium}")
else:
    print("[build] No Chromium found, skipping bundle")
