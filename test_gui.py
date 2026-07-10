#!/usr/bin/env python3
"""GUI测试：启动GUI，验证界面元素和基本交互"""
import os, sys, time, subprocess
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("gui_test")


def test_gui_startup():
    logger.info("=== 测试: GUI启动和基本检查 ===")
    root = tk.Tk()
    root.withdraw()

    from gui import AutoRepeatApp
    app = AutoRepeatApp(root)

    checks = []

    checks.append(("窗口标题", root.title() == "昨日重现 - 示教再现RPA"))

    checks.append(("录制按钮存在", app.btn_record is not None))
    checks.append(("回放按钮存在", app.btn_play is not None))
    checks.append(("暂停按钮存在", app.btn_pause is not None))
    checks.append(("停止按钮存在", app.btn_stop_play is not None))

    checks.append(("初始状态非录制", not app.recording))
    checks.append(("初始状态非回放", not app.playing))
    checks.append(("录制按钮文本", app.btn_record.cget("text") == "录制"))
    checks.append(("回放按钮可用", str(app.btn_play.cget("state")) != "disabled"))
    checks.append(("暂停按钮禁用", str(app.btn_pause.cget("state")) == "disabled"))
    checks.append(("停止按钮禁用", str(app.btn_stop_play.cget("state")) == "disabled"))

    checks.append(("速度默认1.0", app.speed_var.get() == 1.0))
    checks.append(("定向默认开", app.targeted_var.get() == True))
    checks.append(("OCR默认关", app.smart_var.get() == False))
    checks.append(("视觉默认关", app.visual_var.get() == False))

    checks.append(("脚本列表Treeview存在", app.tree is not None))
    checks.append(("编辑器Treeview存在", app.editor_tree is not None))

    checks.append(("ScriptManager存在", app.sm is not None))

    checks.append(("热键tap已注册", app._hotkey_tap is not None))

    root.destroy()

    pass_count = sum(1 for _, ok in checks if ok)
    for name, ok in checks:
        logger.info("  %s: %s", name, "PASS" if ok else "FAIL")

    logger.info("GUI测试: %d/%d 通过", pass_count, len(checks))
    return pass_count, len(checks)


if __name__ == "__main__":
    pass_count, total = test_gui_startup()
    sys.exit(0 if pass_count == total else 1)