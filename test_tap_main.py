#!/usr/bin/env python3
"""Test CGEventTap - main thread CFRunLoop version"""
from Quartz import *
import time, os

count = 0
start = time.time()
stop_time = None

def callback(proxy, event_type, event, refcon):
    global count
    count += 1
    if count <= 5:
        loc = CGEventGetLocation(event)
        print(f"  Event #{count}: type={event_type} at ({loc.x:.0f},{loc.y:.0f})")
    return event

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp) | (1 << kCGEventMouseMoved),
    callback,
    None,
)

if not tap:
    print("ERROR: CGEventTapCreate returned None")
    exit(1)

print(f"CGEventTap created OK")
CGEventTapEnable(tap, True)
source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = CFRunLoopGetCurrent()
CFRunLoopAddSource(rl, source, kCFRunLoopCommonModes)

import threading

def stop_after():
    global stop_time
    time.sleep(5)
    stop_time = time.time()
    CFRunLoopStop(rl)

threading.Thread(target=stop_after, daemon=True).start()

print("Waiting 5s on MAIN THREAD - move mouse and click...")
CFRunLoopRun()

elapsed = (stop_time or time.time()) - start
print(f"Events captured: {count}, Time: {elapsed:.1f}s, Rate: {count/elapsed:.1f} events/s")