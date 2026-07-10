from setuptools import setup
import os
import sys

APP = ["main.py"]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["Quartz", "PIL", "cv2", "mss", "pytesseract", "numpy"],
    "includes": [
        "tkinter",
        "Quartz",
        "PIL",
        "cv2",
        "mss",
        "pytesseract",
        "numpy",
    ],
    "excludes": [
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "notebook",
        "pytest",
        "mypy",
        "setuptools.tests",
        "numpy.testing",
        "numpy._py2tool",
        "distutils.tests",
    ],
    "iconfile": None,
    "plist": {
        "CFBundleName": "昨日重现",
        "CFBundleDisplayName": "昨日重现",
        "CFBundleIdentifier": "com.zrcr.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "12.0",
        "NSAppleEventsUsageDescription": "昨日重现需要控制其他应用以复现操作",
        "NSAccessibilityUsageDescription": "昨日重现需要辅助功能权限以识别和操作界面元素",
        "NSAppleScriptEnabled": True,
    },
    "extra_scripts": [
        os.path.join("src", "gui.py"),
        os.path.join("src", "mac_recorder.py"),
        os.path.join("src", "mac_player.py"),
        os.path.join("src", "accessibility.py"),
        os.path.join("src", "script_manager.py"),
    ],
}

setup(
    name="昨日重现",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)