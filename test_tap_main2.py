#!/usr/bin/env python3
"""Test: CGEventTap on main thread NSRunLoop, other work in sub-thread"""
from Quartz import *
from Foundation import NSRunLoop, NSDate
from CoreFoundation import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, kCFRunLoopDefaultMode
import time, threading

events = []
stop_flag = False

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    if len(events) <= 5:
        print(f"  CB: type={event_type} pos=({loc.x:.0f},{loc.y:.0f})")
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
CGEventTapEnable(tap, True)

source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = NSRunLoop.currentRunLoop().getCFRunLoop()
CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)

def stop_later():
    global stop_flag
    time.sleep(5)
    stop_flag = True

threading.Thread(target=stop_later, daemon=True).start()

print("Running NSRunLoop on MAIN thread for 5s - move mouse and click!")
while not stop_flag:
    NSRunLoop.currentRunLoop().runUntilDate_(
        NSDate.dateWithTimeIntervalSinceNow_(0.05)
    )

print(f"\nEvents captured: {len(events)}")
if len(events) > 0:
    print("SUCCESS! Main thread NSRunLoop works!")
else:
    print("FAILED")