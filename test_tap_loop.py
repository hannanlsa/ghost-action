#!/usr/bin/env python3
"""Test CFRunLoop + CGEventTap integration"""
from Quartz import *
import time, threading

events = []
timer_fired = 0

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    if len(events) <= 10:
        print(f"  CB: type={event_type} pos=({loc.x:.0f},{loc.y:.0f})")
    return event

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp) | (1 << kCGEventMouseMoved),
    callback,
    None,
)
print(f"Tap created: {tap is not None}")
CGEventTapEnable(tap, True)

source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = CFRunLoopGetCurrent()
CFRunLoopAddSource(rl, source, kCFRunLoopCommonModes)

# Add a timer to verify CFRunLoop is working
from CoreFoundation import CFRunLoopTimerCreate, CFRunLoopAddTimer, kCFRunLoopDefaultMode
import time as _time

def timer_callback(timer, info):
    global timer_fired
    timer_fired += 1
    if timer_fired <= 5:
        print(f"  Timer fired #{timer_fired}")

timer = CFRunLoopTimerCreate(None, _time.time() + 1.0, 1.0, 0, 0, timer_callback, None)
CFRunLoopAddTimer(rl, timer, kCFRunLoopDefaultMode)

def stop_later():
    time.sleep(6)
    print("Stopping CFRunLoop...")
    CFRunLoopStop(rl)

threading.Thread(target=stop_later, daemon=True).start()

print("Running CFRunLoop for 6s - move mouse and click!")
start = time.time()
CFRunLoopRun()
elapsed = time.time() - start

print(f"\nResults:")
print(f"  Timer fires: {timer_fired}")
print(f"  Events captured: {len(events)}")
print(f"  Elapsed: {elapsed:.1f}s")
if timer_fired > 0 and len(events) == 0:
    print("DIAGNOSIS: CFRunLoop works (timer fires) but CGEventTap callback never called!")
    print("  This means the tap is created but not receiving events from the system.")
elif timer_fired == 0:
    print("DIAGNOSIS: CFRunLoop not processing any sources at all!")