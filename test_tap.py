#!/usr/bin/env python3
import sys, time
from Quartz import (
    CGEventTapCreate, CGEventTapEnable, CGEventGetLocation, CGEventGetType,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft,
    CGEventCreateMouseEvent, CGEventPost, CGPoint,
    CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
    kCFRunLoopCommonModes, CFRunLoopStop, CFRunLoopRun,
)
import threading

captured = []

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    captured.append((event_type, loc.x, loc.y))
    return event

mask = (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp)
tap = CGEventTapCreate(kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly, mask, callback, None)
if not tap:
    print("FAIL: EventTap failed")
    sys.exit(1)

CGEventTapEnable(tap, True)
source = CFMachPortCreateRunLoopSource(None, tap, 0)
rl = CFRunLoopGetCurrent()
CFRunLoopAddSource(rl, source, kCFRunLoopCommonModes)

t = threading.Thread(target=CFRunLoopRun, daemon=True)
t.start()
time.sleep(0.5)

print("Sending test clicks...")
down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, CGPoint(100, 200), kCGMouseButtonLeft)
up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, CGPoint(100, 200), kCGMouseButtonLeft)
CGEventPost(kCGHIDEventTap, down)
time.sleep(0.05)
CGEventPost(kCGHIDEventTap, up)
time.sleep(1)

print(f"Captured: {len(captured)} events")
for e in captured:
    print(f"  type={e[0]} x={e[1]:.0f} y={e[2]:.0f}")

CFRunLoopStop(rl)