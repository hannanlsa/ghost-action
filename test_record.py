#!/usr/bin/env python3
import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from mac_recorder import MacRecorder
from Quartz import CGEventCreateMouseEvent, CGEventPost, CGPoint, kCGHIDEventTap, kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft
import tempfile

ss_dir = tempfile.mkdtemp()
r = MacRecorder(screenshot_interval=10.0, screenshot_dir=ss_dir, ocr_anchors=True, visual_templates=True)

print("启动录制(5秒, 2秒后自动模拟点击)...")
r.start()

def simulate_clicks():
    time.sleep(2)
    for i in range(3):
        x, y = 500 + i * 100, 400
        down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, CGPoint(x, y), kCGMouseButtonLeft)
        up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, CGPoint(x, y), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, down)
        time.sleep(0.05)
        CGEventPost(kCGHIDEventTap, up)
        time.sleep(0.3)
        print(f"  模拟点击 #{i+1}: ({x}, {y})")

t = threading.Thread(target=simulate_clicks, daemon=True)
t.start()

time.sleep(5)
events = r.stop()
print(f"\n录制完成: {len(events)} 事件")

from collections import Counter
types = Counter(e["type"] for e in events)
for t, c in types.most_common():
    print(f"  {t}: {c}")

for e in events:
    et = e["type"]
    if et == "mouse_down":
        print(f"  点击: ({e['x']:.0f}, {e['y']:.0f}) pid={e.get('pid')} mods={e.get('modifiers', [])}")
        if e.get("ocr_anchor"):
            print(f"    OCR: {e['ocr_anchor']['text']}")
        if e.get("template"):
            print(f"    模板: {e['template']}")
        if e.get("ax_element"):
            print(f"    AX: {e['ax_element'].get('AXRole', '')} {e['ax_element'].get('AXTitle', '')}")
    elif et == "key_down":
        print(f"  按键: keycode={e['keycode']} text={repr(e.get('text', ''))} mods={e.get('modifiers', [])}")
    elif et == "mouse_drag":
        print(f"  拖拽: ({e['x']:.0f}, {e['y']:.0f})")

from script_manager import ScriptManager
sm = ScriptManager()
sm.save("test_real", events, {"duration": 5.0})
print(f"\n脚本已保存: test_real")
