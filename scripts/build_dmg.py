#!/usr/bin/env python3
import os
import subprocess
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
APP_NAME = "GhostAction"
APP_DIR = os.path.join(DIST, f"{APP_NAME}.app")

os.makedirs(DIST, exist_ok=True)

contents_macos = os.path.join(APP_DIR, "Contents", "MacOS")
contents_resources = os.path.join(APP_DIR, "Contents", "Resources")
os.makedirs(contents_macos, exist_ok=True)
os.makedirs(contents_resources, exist_ok=True)

launcher = os.path.join(contents_macos, APP_NAME)
with open(launcher, "w") as f:
    f.write('#!/bin/bash\n')
    f.write('exec /usr/bin/python3 "$(dirname "$0")/../Resources/main.py" "$@"\n')
os.chmod(launcher, 0o755)

src_dir = os.path.join(ROOT, "src")
for fname in os.listdir(src_dir):
    if fname.endswith(".py"):
        shutil.copy2(os.path.join(src_dir, fname), contents_resources)
if os.path.exists(os.path.join(ROOT, "main.py")):
    shutil.copy2(os.path.join(ROOT, "main.py"), contents_resources)

import plistlib
plist = {
    "CFBundleName": APP_NAME,
    "CFBundleDisplayName": "GhostAction",
    "CFBundleIdentifier": "com.ghost-action.app",
    "CFBundleVersion": "1.0.0",
    "CFBundleShortVersionString": "1.0.0",
    "CFBundleExecutable": APP_NAME,
    "CFBundlePackageType": "APPL",
    "LSMinimumSystemVersion": "12.0",
    "NSAccessibilityUsageDescription": "GhostAction needs Accessibility to record and replay mouse/keyboard operations.",
    "NSScreenCaptureUsageDescription": "GhostAction needs Screen Recording to capture window content for visual matching.",
    "LSUIElement": False,
}
with open(os.path.join(APP_DIR, "Contents", "Info.plist"), "wb") as f:
    plistlib.dump(plist, f)

dmg_path = os.path.join(DIST, f"{APP_NAME}.dmg")
if os.path.exists(dmg_path):
    os.remove(dmg_path)

subprocess.run([
    "hdiutil", "create", "-volname", APP_NAME,
    "-srcfolder", APP_DIR, "-ov", "-format", "UDZO",
    dmg_path
], check=True)

print(f"DMG created: {dmg_path}")