#!/usr/bin/env python3
"""Test Tkinter + NSRunLoop pump with synthetic events"""
import sys, os, time, threading
sys.path.insert(0, os.path.dirname(__file__))

from Quartz import *
from Foundation import NSRunLoop, NSDate
from CoreFoundation import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, kCFRunLoopDefaultMode
import tkinter as tk

events = []
stop_flag = False

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    return event

root = tk.Tk()
root.title("NSRunLoop+Tkinter Test")
root.geometry("400x200")

label = tk.Label(root, text="Testing...\nEvents: 0", font=("Arial", 14))
label.pack(expand=True, fill="both")

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventMouseMoved),
    callback,
    None,
)

if tap:
    CGEventTapEnable(tap, True)
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    rl = NSRunLoop.currentRunLoop().getCFRunLoop()
    CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)
    print("CGEventTap registered on main NSRunLoop")
else:
    print("ERROR: Tap creation failed")

def post_synthetic_events():
    time.sleep(1.0)
    print("Posting synthetic mouse events...")
    for i in range(20):
        pt = (500 + i * 5, 300 + i * 3)
        event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, pt, 0)
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(0.05)
    time.sleep(1.0)
    print(f"Total events captured: {len(events)}")
    root.after(0, root.destroy)

threading.Thread(target=post_synthetic_events, daemon=True).start()

def pump_ns_runloop():
    try:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.02)
        )
    except Exception:
        pass
    label.config(text=f"Testing...\nEvents: {len(events)}")
    root.after(50, pump_ns_runloop)

pump_ns_runloop()
print("Starting Tkinter mainloop...")
root.mainloop()
print(f"Final events: {len(events)}")
if len(events) > 0:
    print("SUCCESS! Tkinter + NSRunLoop pump works!")
else:
    print("FAILED - no events captured")