#!/usr/bin/env python3
"""Test CGEventTap capture rate"""
from Quartz import *
import time, os, threading

count = 0
start = time.time()

def callback(proxy, event_type, event, refcon):
    global count
    count += 1
    return event

tap = CGEventTapCreate(
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    (1 << kCGEventKeyDown) | (1 << kCGEventLeftMouseDown) | (1 << kCGEventMouseMoved),
    callback,
    None,
)

if not tap:
    print("ERROR: CGEventTapCreate returned None - need Accessibility permission!")
else:
    print(f"CGEventTap created OK")
    CGEventTapEnable(tap, True)
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    rl = CFRunLoopGetCurrent()
    CFRunLoopAddSource(rl, source, kCFRunLoopCommonModes)
    
    def run_loop():
        CFRunLoopRun()
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    
    print("Waiting 5s - move mouse and click...")
    time.sleep(5)
    
    CGEventTapEnable(tap, False)
    CFRunLoopStop(rl)
    
    elapsed = time.time() - start
    print(f"Events captured: {count}, Time: {elapsed:.1f}s, Rate: {count/elapsed:.1f} events/s")