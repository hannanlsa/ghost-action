#!/usr/bin/env python3
"""端到端测试：录制→回放→验证，不启动GUI窗口"""
import os
import sys
import time
import logging
import subprocess
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(os.path.join(LOGS_DIR, "test_e2e.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("e2e_test")


def kill_old():
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "python3" in line and "main.py" in line and "grep" not in line:
            pid = line.split()[1]
            logger.info("杀旧进程 PID=%s", pid)
            subprocess.run(["kill", "-9", pid], capture_output=True)
    time.sleep(1)


def test_record_and_play():
    from mac_recorder import MacRecorder
    from mac_player import MacPlayer
    from script_manager import ScriptManager

    script_name = "e2e_test_1"
    ss_dir = os.path.join(BASE_DIR, "scripts", f"{script_name}_screenshots")

    logger.info("=" * 60)
    logger.info("步骤1: 启动录制器")
    recorder = MacRecorder(
        screenshot_interval=999,
        screenshot_dir=ss_dir,
        ocr_anchors=False,
        visual_templates=False,
    )
    recorder.start()
    logger.info("录制器已启动，等待2秒...")
    time.sleep(2)

    logger.info("步骤2: 用AppleScript模拟用户点击（Finder窗口）")
    click_x, click_y = 400, 300
    applescript = f'tell application "System Events" to click at {{{click_x}, {click_y}}}'
    result = subprocess.run(
        ["osascript", "-e", applescript],
        capture_output=True, text=True, timeout=10,
    )
    logger.info("AppleScript结果: rc=%d stderr=%s", result.returncode, result.stderr.strip())
    time.sleep(1)

    logger.info("步骤3: 模拟键盘输入（打开Spotlight: Cmd+Space）")
    applescript2 = 'tell application "System Events" to keystroke " " using command down'
    result2 = subprocess.run(
        ["osascript", "-e", applescript2],
        capture_output=True, text=True, timeout=10,
    )
    logger.info("AppleScript键盘结果: rc=%d stderr=%s", result2.returncode, result2.stderr.strip())
    time.sleep(1)

    logger.info("步骤4: 关闭Spotlight（按Escape）")
    applescript3 = 'tell application "System Events" to key code 53'
    result3 = subprocess.run(
        ["osascript", "-e", applescript3],
        capture_output=True, text=True, timeout=10,
    )
    time.sleep(1)

    logger.info("步骤5: 停止录制")
    events = recorder.stop()
    logger.info("录制完成，共 %d 事件", len(events))

    for i, e in enumerate(events):
        etype = e.get("type", "")
        detail = ""
        if "x" in e:
            detail += f" ({e['x']:.0f},{e['y']:.0f})"
        if "keycode" in e:
            detail += f" kc={e['keycode']}"
        if "text" in e:
            detail += f" text='{e['text']}'"
        if "modifiers" in e:
            detail += f" mods={e['modifiers']}"
        logger.info("  事件[%d]: %s%s", i, etype, detail)

    mouse_events = [e for e in events if e["type"] in ("mouse_down", "mouse_up")]
    key_events = [e for e in events if e["type"] in ("key_down", "key_up")]
    logger.info("鼠标事件: %d, 键盘事件: %d", len(mouse_events), len(key_events))

    if len(events) == 0:
        logger.error("BUG: 录制0事件！AppleScript模拟的操作未被CGEventTap捕获")
        logger.error("可能原因: CGEventTap在ListenOnly模式下无法捕获osascript发出的事件")
        logger.info("尝试用CGEventPost直接发送事件...")
        return test_with_cg_event_post()

    logger.info("步骤6: 保存脚本")
    sm = ScriptManager()
    meta = {"clicks": len(mouse_events), "keys": len(key_events), "duration": 5.0}
    sm.save(script_name, events, meta)

    logger.info("步骤7: 回放脚本")
    player = MacPlayer(
        speed=1.0,
        target_pid=None,
        smart_replay=False,
        visual_match=False,
        scripts_dir=BASE_DIR,
        retry_count=1,
        on_error="continue",
    )
    player.play(events, variables={})
    logger.info("回放完成")

    ok_count = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail_count = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("回放结果: %d成功, %d失败", ok_count, fail_count)

    logger.info("=" * 60)
    logger.info("端到端测试完成")
    return True


def test_with_cg_event_post():
    """用CGEventPost直接发送事件，绕过AppleScript"""
    from Quartz import (
        CGEventCreateMouseEvent, CGEventPost, kCGHIDEventTap,
        kCGEventLeftMouseDown, kCGEventLeftMouseUp,
        CGEventCreateKeyboardEvent,
    )

    from mac_recorder import MacRecorder
    from mac_player import MacPlayer

    script_name = "e2e_test_cgpost"
    ss_dir = os.path.join(BASE_DIR, "scripts", f"{script_name}_screenshots")

    logger.info("=" * 60)
    logger.info("备用方案: 用CGEventPost直接发送事件")

    recorder = MacRecorder(
        screenshot_interval=999,
        screenshot_dir=ss_dir,
        ocr_anchors=False,
        visual_templates=False,
    )
    recorder.start()
    time.sleep(1)

    click_x, click_y = 500, 400
    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (click_x, click_y), 0)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, (click_x, click_y), 0)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.1)
    CGEventPost(kCGHIDEventTap, up)
    time.sleep(0.5)

    SPACE_KEYCODE = 49
    key_down = CGEventCreateKeyboardEvent(None, SPACE_KEYCODE, True)
    key_up = CGEventCreateKeyboardEvent(None, SPACE_KEYCODE, False)
    CGEventPost(kCGHIDEventTap, key_down)
    time.sleep(0.1)
    CGEventPost(kCGHIDEventTap, key_up)
    time.sleep(0.5)

    events = recorder.stop()
    logger.info("CGEventPost录制完成，共 %d 事件", len(events))

    for i, e in enumerate(events):
        etype = e.get("type", "")
        detail = ""
        if "x" in e:
            detail += f" ({e['x']:.0f},{e['y']:.0f})"
        if "keycode" in e:
            detail += f" kc={e['keycode']}"
        logger.info("  事件[%d]: %s%s", i, etype, detail)

    mouse_events = [e for e in events if e["type"] in ("mouse_down", "mouse_up")]
    key_events = [e for e in events if e["type"] in ("key_down", "key_up")]
    logger.info("鼠标事件: %d, 键盘事件: %d", len(mouse_events), len(key_events))

    if len(events) == 0:
        logger.error("严重BUG: CGEventPost发出的事件也未被捕获！")
        logger.error("这说明CGEventTap在ListenOnly模式下无法捕获自己进程发出的事件")
        return False

    logger.info("CGEventPost方案成功！录制了 %d 事件", len(events))

    from script_manager import ScriptManager
    sm = ScriptManager()
    meta = {"clicks": len(mouse_events), "keys": len(key_events), "duration": 3.0}
    sm.save(script_name, events, meta)

    player = MacPlayer(
        speed=1.0,
        target_pid=None,
        smart_replay=False,
        visual_match=False,
        scripts_dir=BASE_DIR,
        retry_count=1,
        on_error="continue",
    )
    player.play(events, variables={})
    ok_count = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail_count = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("回放结果: %d成功, %d失败", ok_count, fail_count)

    return True


if __name__ == "__main__":
    kill_old()
    try:
        ok = test_record_and_play()
        sys.exit(0 if ok else 1)
    except Exception as e:
        logger.critical("测试崩溃: %s", e, exc_info=True)
        sys.exit(2)