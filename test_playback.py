#!/usr/bin/env python3
"""回放器功能测试：用合成事件列表测试回放器的所有功能"""
import os, sys, time, logging
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from mac_player import MacPlayer
from script_manager import ScriptManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("playback_test")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def test_basic_playback():
    logger.info("=== 测试1: 基础鼠标点击回放 ===")
    events = [
        {"type": "mouse_down", "button": "left", "x": 400, "y": 300, "time": 0.0},
        {"type": "mouse_up", "button": "left", "x": 400, "y": 300, "time": 0.1},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok == 2


def test_keyboard_playback():
    logger.info("=== 测试2: 键盘回放 ===")
    events = [
        {"type": "key_down", "keycode": 49, "modifiers": ["cmd"], "time": 0.0},
        {"type": "key_up", "keycode": 49, "modifiers": ["cmd"], "time": 0.1},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok == 2


def test_text_input():
    logger.info("=== 测试3: 文本输入回放 ===")
    events = [
        {"type": "type_text", "text": "hello", "time": 0.0},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok == 1


def test_scroll():
    logger.info("=== 测试4: 滚轮回放 ===")
    events = [
        {"type": "scroll", "dx": 0, "dy": -3, "x": 400, "y": 300, "time": 0.0},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok == 1


def test_drag():
    logger.info("=== 测试5: 拖拽回放 ===")
    events = [
        {"type": "mouse_down", "button": "left", "x": 200, "y": 200, "time": 0.0},
        {"type": "mouse_drag", "button": "left", "x": 400, "y": 400, "time": 0.5},
        {"type": "mouse_up", "button": "left", "x": 400, "y": 400, "time": 1.0},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok == 3


def test_control_flow():
    logger.info("=== 测试6: 控制流（循环+变量） ===")
    events = [
        {"type": "for", "count": 2, "variable": "i", "time": 0.0},
        {"type": "mouse_down", "button": "left", "x": 300, "y": 300, "time": 0.1},
        {"type": "mouse_up", "button": "left", "x": 300, "y": 300, "time": 0.2},
        {"type": "endfor", "time": 0.3},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败 (期望4ok: 1for+2*(mousedown+mouseup)+1endfor)", ok, fail)
    return ok >= 4


def test_comment_and_activate():
    logger.info("=== 测试7: 注释+激活窗口 ===")
    events = [
        {"type": "comment", "text": "test comment", "time": 0.0},
        {"type": "activate", "pid": 0, "bundle_id": "com.apple.Finder", "time": 0.1},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    fail = sum(1 for l in player.execution_log if l.get("status") == "fail")
    logger.info("结果: %d成功 %d失败", ok, fail)
    return ok >= 1


def test_pause_resume():
    logger.info("=== 测试8: 暂停/继续 ===")
    events = [
        {"type": "mouse_down", "button": "left", "x": 100, "y": 100, "time": 0.0},
        {"type": "mouse_up", "button": "left", "x": 100, "y": 100, "time": 0.1},
        {"type": "mouse_down", "button": "left", "x": 200, "y": 200, "time": 0.5},
        {"type": "mouse_up", "button": "left", "x": 200, "y": 200, "time": 0.6},
    ]
    player = MacPlayer(speed=1.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")

    import threading
    def delayed_pause():
        time.sleep(0.3)
        player.pause()
        time.sleep(0.5)
        player.resume()

    threading.Thread(target=delayed_pause, daemon=True).start()
    player.play(events, variables={})
    ok = sum(1 for l in player.execution_log if l.get("status") == "ok")
    logger.info("结果: %d成功", ok)
    return ok == 4


def test_execution_report():
    logger.info("=== 测试9: 执行报告 ===")
    events = [
        {"type": "mouse_down", "button": "left", "x": 100, "y": 100, "time": 0.0},
        {"type": "mouse_up", "button": "left", "x": 100, "y": 100, "time": 0.1},
    ]
    player = MacPlayer(speed=10.0, target_pid=None, smart_replay=False, visual_match=False,
                       scripts_dir=BASE_DIR, retry_count=1, on_error="continue")
    player.play(events, variables={})
    report = player.generate_report("test_report")
    has_html = "<html" in report or "<!DOCTYPE" in report
    logger.info("报告生成: %s (长度=%d)", "成功" if has_html else "失败", len(report))
    return has_html


def test_script_manager():
    logger.info("=== 测试10: 脚本管理器 ===")
    sm = ScriptManager()
    test_events = [
        {"type": "mouse_down", "button": "left", "x": 100, "y": 100, "time": 0.0},
        {"type": "mouse_up", "button": "left", "x": 100, "y": 100, "time": 0.1},
    ]
    sm.save("test_sm_script", test_events, {"clicks": 1})
    data = sm.load("test_sm_script")
    ok = data is not None and len(data.get("events", [])) == 2
    sm.delete("test_sm_script")
    data2 = sm.load("test_sm_script")
    ok2 = data2 is None
    logger.info("脚本保存/加载/删除: %s", "成功" if ok and ok2 else "失败")
    return ok and ok2


if __name__ == "__main__":
    tests = [
        ("基础鼠标点击", test_basic_playback),
        ("键盘回放", test_keyboard_playback),
        ("文本输入", test_text_input),
        ("滚轮回放", test_scroll),
        ("拖拽回放", test_drag),
        ("控制流", test_control_flow),
        ("注释+激活窗口", test_comment_and_activate),
        ("暂停/继续", test_pause_resume),
        ("执行报告", test_execution_report),
        ("脚本管理器", test_script_manager),
    ]

    results = []
    for name, fn in tests:
        try:
            ok = fn()
            results.append((name, "PASS" if ok else "FAIL"))
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("回放器测试结果")
    print("=" * 60)
    pass_count = 0
    for name, status in results:
        print(f"  {name}: {status}")
        if status == "PASS":
            pass_count += 1
    print(f"\n通过: {pass_count}/{len(results)}")