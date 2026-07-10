#!/usr/bin/env python3
"""Test the fixed MacRecorder with NSRunLoop"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.dirname(__file__))

from mac_recorder import MacRecorder
import time

recorder = MacRecorder(
    screenshot_interval=2.0,
    screenshot_dir=os.path.join(os.path.expanduser("~"), "昨日重现", "test_screenshots"),
    ocr_anchors=True,
    visual_templates=True,
)

print("Starting recorder for 5s - move mouse and click!")
recorder.start()
time.sleep(5)
events = recorder.stop()

print(f"\nEvents captured: {len(events)}")
for i, ev in enumerate(events[:10]):
    print(f"  [{i}] {ev.get('type')} at ({ev.get('x', '?')}, {ev.get('y', '?')}) t={ev.get('time', 0):.2f}s")
if len(events) > 10:
    print(f"  ... and {len(events) - 10} more")

if len(events) > 10:
    print("\nSUCCESS! Recorder is working with NSRunLoop!")
else:
    print("\nFAILED - still not capturing enough events")