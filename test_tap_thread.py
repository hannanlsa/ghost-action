#!/usr/bin/env python3
"""Minimal test: NSRunLoop + CGEventTap in a thread"""
from Quartz import *
from Foundation import NSRunLoop, NSDate
from CoreFoundation import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, kCFRunLoopDefaultMode
import time, threading

events = []
recording = True

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    if len(events) <= 5:
        print(f"  CB: type={event_type} pos=({loc.x:.0f},{loc.y:.0f})")
    return event

def run_tap_thread():
    tap = CGEventTapCreate(
        kCGHIDEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionListenOnly,
        (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventMouseMoved),
        callback,
        None,
    )
    if not tap:
        print("ERROR: Tap creation failed!")
        return
    
    print(f"Thread: Tap created OK")
    CGEventTapEnable(tap, True)
    
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    rl = NSRunLoop.currentRunLoop().getCFRunLoop()
    CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)
    
    print(f"Thread: Running NSRunLoop...")
    while recording:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.05)
        )
    print(f"Thread: Exiting")

t = threading.Thread(target=run_tap_thread, daemon=True)
t.start()

print("Main: Waiting 5s - move mouse and click!")
time.sleep(5)
recording = False
t.join(timeout=2)

print(f"\nEvents captured: {len(events)}")
if len(events) > 0:
    print("SUCCESS!")
else:
    print("FAILED - no events in thread either")