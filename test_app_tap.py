#!/usr/bin/env python3
"""Test CGEventTap from within the APP's Python environment"""
import sys, os

# Use the APP's Python
app_python = "/Applications/昨日重现.app/Contents/Frameworks/Python.framework/Versions/3.14/bin/python3.14"
if not os.path.exists(app_python):
    app_python = sys.executable
    print(f"APP Python not found, using: {app_python}")

# Run test in APP's Python context
test_code = '''
from Quartz import CGEventTapCreate, kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly, kCGEventKeyDown
from ApplicationServices import AXIsProcessTrusted

print(f"AXIsProcessTrusted: {AXIsProcessTrusted()}")

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown),
    lambda proxy, etype, event, refcon: event,
    None,
)
print(f"CGEventTapCreate result: {tap}")
print(f"Type: {type(tap)}")
if tap:
    print("SUCCESS - tap created!")
else:
    print("FAILED - tap is None")
    # Try Default mode instead of ListenOnly
    tap2 = CGEventTapCreate(
        kCGHIDEventTap,
        kCGHeadInsertEventTap,
        0,  # kCGEventTapOptionDefault
        (1 << kCGEventKeyDown),
        lambda proxy, etype, event, refcon: event,
        None,
    )
    print(f"Default mode tap: {tap2}")
'''

import subprocess
result = subprocess.run([app_python, "-c", test_code], capture_output=True, text=True, timeout=10)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])