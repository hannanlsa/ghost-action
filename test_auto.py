#!/usr/bin/env python3
"""自动化测试：录制→保存→回放→验证，全程日志"""
import sys, os, time, json, logging, logging.handlers, traceback, tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.handlers.RotatingFileHandler(
            os.path.join(LOGS_DIR, "test_auto.log"), maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
        ),
        logging.StreamHandler(sys.stderr),
    ]
)
logger = logging.getLogger("test_auto")

BUGS = []

def bug(desc, detail=""):
    BUGS.append({"desc": desc, "detail": detail})
    logger.error("BUG: %s | %s", desc, detail)

def test_recorder():
    logger.info("=== 测试1: 录制器 ===")
    from mac_recorder import MacRecorder
    ss_dir = tempfile.mkdtemp()
    r = MacRecorder(screenshot_interval=10.0, screenshot_dir=ss_dir, ocr_anchors=True, visual_templates=True)
    
    try:
        r.start()
        logger.info("录制器启动成功")
    except RuntimeError as e:
        bug("录制器启动失败", str(e))
        return None
    
    time.sleep(2)
    events = r.stop()
    logger.info("录制器停止, %d 事件", len(events))
    
    if len(events) == 0:
        logger.warning("0事件 - 可能是因为没有用户操作(正常，非bug)")
    else:
        from collections import Counter
        types = Counter(e["type"] for e in events)
        for t, c in types.most_common():
            logger.info("  %s: %d", t, c)
        
        for e in events:
            if e["type"] == "mouse_down":
                if e.get("pid") is None:
                    bug("mouse_down缺少pid", f"x={e.get('x')} y={e.get('y')}")
                if e.get("modifiers") is None:
                    bug("mouse_down缺少modifiers字段")
                if e.get("template") is None and r.visual_templates:
                    bug("mouse_down缺少template", f"visual_templates=True但无模板")
            elif e["type"] == "key_down":
                if e.get("text") is None:
                    bug("key_down缺少text字段", f"keycode={e.get('keycode')}")
    
    return events

def test_script_manager(events):
    logger.info("=== 测试2: 脚本管理 ===")
    from script_manager import ScriptManager
    sm = ScriptManager()
    
    if not events:
        events = [{"type": "comment", "text": "test", "time": 0}]
    
    sm.save("auto_test", events, {"duration": 2.0})
    data = sm.load("auto_test")
    
    if not data:
        bug("脚本保存/加载失败")
        return None
    
    if data.get("event_count") != len(events):
        bug("event_count不匹配", f"saved={data.get('event_count')} actual={len(events)}")
    
    logger.info("脚本保存/加载成功: %d 事件", len(data.get("events", [])))
    return data

def test_player(data):
    logger.info("=== 测试3: 回放器 ===")
    from mac_player import MacPlayer
    
    events = data.get("events", [])
    scripts_dir = os.path.dirname(BASE_DIR)
    
    p = MacPlayer(speed=100.0, retry_count=1, on_error="continue", scripts_dir=scripts_dir)
    
    try:
        p.play(events, variables={})
        logger.info("回放完成: %d 成功, %d 失败",
                    sum(1 for l in p.execution_log if l.get("status") == "ok"),
                    sum(1 for l in p.execution_log if l.get("status") == "fail"))
    except Exception as e:
        bug("回放器崩溃", str(e))
        logger.error("堆栈: %s", traceback.format_exc())
        return p
    
    for log_entry in p.execution_log:
        if log_entry.get("status") == "fail":
            bug("回放步骤失败", f"step={log_entry.get('step')} type={log_entry.get('type')} error={log_entry.get('error')}")
    
    report = p.generate_report("auto_test")
    report_path = os.path.join(LOGS_DIR, "test_report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("执行报告: %s", report_path)
    
    return p

def test_accessibility():
    logger.info("=== 测试4: Accessibility ===")
    from accessibility import get_element_at_point, get_element_attrs, get_element_actions
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    
    wl = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    tested = 0
    for w in wl:
        pid = w.get('kCGWindowOwnerPID', -1)
        owner = w.get('kCGWindowOwnerName', '')
        layer = w.get('kCGWindowLayer', -1)
        if layer != 0 or not owner or pid < 0:
            continue
        b = w.get('kCGWindowBounds', {})
        ww, wh = b.get('Width', 0), b.get('Height', 0)
        if ww * wh < 100:
            continue
        cx = int(b.get('X', 0) + ww // 2)
        cy = int(b.get('Y', 0) + wh // 2)
        if cx < 0 or cy < 0:
            continue
        
        elem = get_element_at_point(pid, cx, cy)
        if elem:
            attrs = get_element_attrs(elem)
            if attrs:
                logger.info("  %s PID=%d: %s", owner, pid, attrs.get("AXRole", "?"))
            actions = get_element_actions(elem)
            if actions:
                logger.info("    actions: %s", actions)
        tested += 1
        if tested >= 5:
            break
    
    logger.info("Accessibility测试完成, 测试了 %d 个窗口", tested)

def test_gui_init():
    logger.info("=== 测试5: GUI初始化 ===")
    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()
        from gui import AutoRepeatApp
        app = AutoRepeatApp(root)
        logger.info("GUI初始化成功")
        
        # 测试编辑器功能
        app._current_events = [
            {"type": "mouse_down", "x": 100, "y": 200, "button": "left", "time": 0},
            {"type": "for", "count": 3, "variable": "i", "time": 0.1},
            {"type": "set_variable", "name": "x", "value_from": "literal", "value": "test", "time": 0.2},
            {"type": "endfor", "time": 0.3},
        ]
        app._populate_editor()
        logger.info("编辑器填充成功")
        
        root.destroy()
    except Exception as e:
        bug("GUI初始化失败", str(e))
        logger.error("堆栈: %s", traceback.format_exc())

def test_player_control_flow():
    logger.info("=== 测试6: 控制流 ===")
    from mac_player import MacPlayer
    
    p = MacPlayer(speed=100.0)
    
    # for循环
    events = [
        {"type": "for", "count": 3, "variable": "i", "time": 0},
        {"type": "set_variable", "name": "x", "value_from": "literal", "value": "v", "time": 0},
        {"type": "endfor", "time": 0},
    ]
    p.play(events, variables={})
    if len(p.execution_log) != 3:
        bug("for循环执行次数不对", f"expected=3 got={len(p.execution_log)}")
    else:
        logger.info("for循环: 3次 OK")
    
    # 嵌套if
    p2 = MacPlayer(speed=100.0)
    events2 = [
        {"type": "if", "strategy": "color", "x": 99999, "y": 99999, "color": [255,0,0], "time": 0},
        {"type": "set_variable", "name": "skip", "value_from": "literal", "value": "1", "time": 0},
        {"type": "endif", "time": 0},
        {"type": "set_variable", "name": "after", "value_from": "literal", "value": "2", "time": 0},
    ]
    p2.play(events2, variables={})
    if p2.variables.get("after") != "2":
        bug("if条件分支后变量未设置")
    else:
        logger.info("if条件分支: OK")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("自动化测试开始")
    logger.info("=" * 60)
    
    try:
        test_accessibility()
    except Exception as e:
        bug("Accessibility测试异常", str(e))
    
    try:
        events = test_recorder()
    except Exception as e:
        bug("录制器测试异常", str(e))
        events = None
    
    try:
        data = test_script_manager(events)
    except Exception as e:
        bug("脚本管理测试异常", str(e))
        data = None
    
    try:
        if data:
            test_player(data)
    except Exception as e:
        bug("回放器测试异常", str(e))
    
    try:
        test_gui_init()
    except Exception as e:
        bug("GUI测试异常", str(e))
    
    try:
        test_player_control_flow()
    except Exception as e:
        bug("控制流测试异常", str(e))
    
    logger.info("=" * 60)
    logger.info("测试完成, 发现 %d 个BUG", len(BUGS))
    for i, b in enumerate(BUGS):
        logger.info("  BUG#%d: %s | %s", i+1, b["desc"], b["detail"])
    logger.info("=" * 60)