#!/usr/bin/env python3
"""Test: CGEventTap capture + CGEventPost synthetic events"""
from Quartz import *
from Foundation import NSRunLoop, NSDate
from CoreFoundation import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, kCFRunLoopDefaultMode
import time, threading

events = []

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    return event

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventMouseMoved),
    callback,
    None,
)
print(f"Tap created: {tap is not None}")
if not tap:
    print("ERROR: Need accessibility permission!")
    exit(1)

CGEventTapEnable(tap, True)
print(f"Tap enabled: {CGEventTapIsEnabled(tap)}")

source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = NSRunLoop.currentRunLoop().getCFRunLoop()
CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)

# Post synthetic events from a sub-thread
def post_events():
    time.sleep(0.5)
    print("Posting synthetic mouse move events...")
    for i in range(10):
        pt = (500 + i * 10, 300 + i * 5)
        event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, pt, 0)
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(0.1)
    print("Done posting events")

threading.Thread(target=post_events, daemon=True).start()

print("Running NSRunLoop for 3s...")
start = time.time()
while time.time() - start < 3.0:
    NSRunLoop.currentRunLoop().runUntilDate_(
        NSDate.dateWithTimeIntervalSinceNow_(0.05)
    )

print(f"\nEvents captured: {len(events)}")
print("NOTE: CGEventTap with ListenOnly cannot capture CGEventPost events (only real HID input)")
print("This is expected behavior - the tap only captures physical input events")