#!/usr/bin/env python3
"""Test CFRunLoopRunInMode vs CFRunLoopRun"""
from Quartz import *
from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode, CFRunLoopTimerCreate, CFRunLoopAddTimer
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

source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = CFRunLoopGetCurrent()
CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)

def timer_callback(timer, info):
    global timer_fired
    timer_fired += 1
    if timer_fired <= 5:
        print(f"  Timer fired #{timer_fired}")

timer = CFRunLoopTimerCreate(None, time.time() + 0.5, 0.5, 0, 0, timer_callback, None)
CFRunLoopAddTimer(rl, timer, kCFRunLoopDefaultMode)

print("Running CFRunLoopRunInMode loop for 5s - move mouse and click!")
start = time.time()
deadline = start + 5.0

while time.time() < deadline:
    result = CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.1, False)
    if events and len(events) > 100:
        break

elapsed = time.time() - start
print(f"\nResults:")
print(f"  Timer fires: {timer_fired}")
print(f"  Events captured: {len(events)}")
print(f"  Elapsed: {elapsed:.1f}s")
if timer_fired > 0 and len(events) == 0:
    print("DIAGNOSIS: CFRunLoop works but CGEventTap not delivering events")
elif timer_fired == 0 and len(events) == 0:
    print("DIAGNOSIS: CFRunLoop not processing sources at all")
elif len(events) > 0:
    print("DIAGNOSIS: Everything works! The issue was CFRunLoopRun() blocking")