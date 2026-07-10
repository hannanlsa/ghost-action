#!/usr/bin/env python3
"""Test with PyObjC bridge - check if CFRunLoop sources work at all"""
import objc
from Quartz import *
from CoreFoundation import (
    CFRunLoopGetCurrent, CFRunLoopAddSource, CFRunLoopRunInMode,
    kCFRunLoopDefaultMode, CFRunLoopTimerCreate, CFRunLoopAddTimer,
    CFMachPortCreateRunLoopSource,
)
import time

events = []
timer_fired = 0

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    return event

def timer_cb(ctimer, info):
    global timer_fired
    timer_fired += 1
    print(f"  Timer #{timer_fired}")

# Method 1: Create tap with pyobjc
tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventMouseMoved),
    callback,
    None,
)
print(f"Tap: {tap}")
print(f"Tap type: {type(tap)}")

if tap:
    enabled = CGEventTapEnable(tap, True)
    print(f"Enable result: {enabled}")
    
    # Check if tap is actually enabled
    is_enabled = CGEventTapIsEnabled(tap)
    print(f"Tap is enabled: {is_enabled}")
    
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    print(f"Source: {source}")
    print(f"Source type: {type(source)}")
    
    rl = CFRunLoopGetCurrent()
    CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)
    
    timer = CFRunLoopTimerCreate(None, time.time() + 0.5, 0.5, 0, 0, timer_cb, None)
    CFRunLoopAddTimer(rl, timer, kCFRunLoopDefaultMode)
    
    print("\nRunning loop for 5s...")
    start = time.time()
    while time.time() - start < 5.0:
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.05, False)
    
    print(f"\nTimer: {timer_fired}, Events: {len(events)}")
    
    # Try kCFRunLoopCommonModes
    print("\n--- Trying kCFRunLoopCommonModes ---")
    CFRunLoopAddSource(rl, source, kCFRunLoopCommonModes)
    
    start2 = time.time()
    while time.time() - start2 < 5.0:
        CFRunLoopRunInMode(kCFRunLoopCommonModes, 0.05, False)
    
    print(f"Timer: {timer_fired}, Events: {len(events)}")