#!/usr/bin/env python3
"""Test GUI + NSRunLoop pump integration"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from Quartz import *
from Foundation import NSRunLoop, NSDate
from CoreFoundation import CFMachPortCreateRunLoopSource, CFRunLoopAddSource, kCFRunLoopDefaultMode
import tkinter as tk
import time, threading

events = []

def callback(proxy, event_type, event, refcon):
    loc = CGEventGetLocation(event)
    events.append((event_type, loc.x, loc.y))
    return event

root = tk.Tk()
root.title("NSRunLoop + Tkinter Test")
root.geometry("400x200")

label = tk.Label(root, text="Move mouse and click!\nEvents: 0", font=("Arial", 14))
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

def pump_ns_runloop():
    try:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.02)
        )
    except Exception:
        pass
    label.config(text=f"Move mouse and click!\nEvents: {len(events)}")
    root.after(50, pump_ns_runloop)

pump_ns_runloop()
print("Starting Tkinter mainloop...")
root.mainloop()
print(f"Final events: {len(events)}")