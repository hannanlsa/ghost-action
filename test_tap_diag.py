#!/usr/bin/env python3
"""Diagnose CGEventTap issues"""
from Quartz import *
import sys

print("=== CGEventTap Diagnostics ===")

# Test 1: Check if we can create the tap
tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventLeftMouseDown),
    lambda proxy, etype, event, refcon: event,
    None,
)
print(f"1. CGEventTapCreate (ListenOnly): {'OK' if tap else 'FAILED'}")

if tap:
    CGEventTapEnable(tap, True)
    print(f"2. CGEventTapEnable: done")

# Test 2: Try Default (non-listen-only) mode
tap2 = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    (1 << kCGEventLeftMouseDown),
    lambda proxy, etype, event, refcon: event,
    None,
)
print(f"3. CGEventTapCreate (Default): {'OK' if tap2 else 'FAILED'}")

# Test 3: Check AXIsProcessTrusted
try:
    trusted = AXIsProcessTrusted()
    print(f"4. AXIsProcessTrusted: {trusted}")
except Exception as e:
    print(f"4. AXIsProcessTrusted: ERROR - {e}")

# Test 4: Check AXIsProcessTrustedWithOptions
try:
    options = {kAXTrustedCheckOptionPrompt: False}
    trusted2 = AXIsProcessTrustedWithOptions(options)
    print(f"5. AXIsProcessTrustedWithOptions: {trusted2}")
except Exception as e:
    print(f"5. AXIsProcessTrustedWithOptions: ERROR - {e}")

# Test 5: Try Session event tap
tap3 = CGEventTapCreate(
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventLeftMouseDown),
    lambda proxy, etype, event, refcon: event,
    None,
)
print(f"6. CGEventTapCreate (Session): {'OK' if tap3 else 'FAILED'}")

# Test 6: Check current process info
import os
print(f"7. PID: {os.getpid()}")
print(f"8. Process name: {os.path.basename(sys.argv[0])}")

# Test 7: Try posting and reading back
try:
    loc = CGEventGetLocation(CGEventCreateMouseEvent(None, kCGEventMouseMoved, (100, 100), 0))
    print(f"9. CGEventGetLocation works: ({loc.x:.0f}, {loc.y:.0f})")
except Exception as e:
    print(f"9. CGEventGetLocation: ERROR - {e}")

# Test 8: Check event tap mask
print(f"10. EVENT_MASK check: kCGEventLeftMouseDown={kCGEventLeftMouseDown}")

print("\n=== Diagnosis ===")
if not tap and not tap2:
    print("RESULT: No accessibility permission! Grant it in System Settings > Privacy & Security > Accessibility")
elif tap and not tap2:
    print("RESULT: Listen-only works but Default mode blocked - partial permission")
elif tap and tap2:
    print("RESULT: Both modes work - permission OK, issue is elsewhere (CFRunLoop?)")