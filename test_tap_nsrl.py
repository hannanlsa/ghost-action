#!/usr/bin/env python3
"""Test with explicit NSRunLoop instead of CFRunLoop"""
from Quartz import *
import time, threading

events = []
timer_fired = 0

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

# Use NSRunLoop instead of CFRunLoop
from Foundation import NSRunLoop, NSDate, NSDefaultRunLoopMode

source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = NSRunLoop.currentRunLoop().getCFRunLoop()
CFRunLoopAddSource(rl, source, NSDefaultRunLoopMode)

print(f"NSRunLoop: {NSRunLoop.currentRunLoop()}")
print("Running NSRunLoop for 5s - move mouse and click!")

start = time.time()
while time.time() - start < 5.0:
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))

elapsed = time.time() - start
print(f"\nEvents captured: {len(events)}")
if len(events) > 0:
    print("SUCCESS! NSRunLoop approach works!")
else:
    print("FAILED - still no events with NSRunLoop")