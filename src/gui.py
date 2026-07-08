import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import platform
import logging
import json
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

import marketplace as mp

IS_MAC = platform.system() == "Darwin"


class _ChineseDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initialvalue="", input_type="string"):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=15)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=prompt).pack(anchor="w", pady=(0, 8))
        if input_type == "integer":
            self._var = tk.StringVar(value=str(initialvalue) if initialvalue else "0")
        else:
            self._var = tk.StringVar(value=str(initialvalue) if initialvalue else "")
        self._entry = ttk.Entry(frm, textvariable=self._var, width=30)
        self._entry.pack(fill="x", pady=(0, 12))
        self._entry.select_range(0, "end")
        self._entry.focus_set()
        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill="x")
        ttk.Button(btn_frm, text="确定", width=8, command=self._on_ok).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frm, text="取消", width=8, command=self._on_cancel).pack(side="right")
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")
        self.wait_window()

    def _on_ok(self):
        val = self._var.get().strip()
        if not val:
            self.result = None
        else:
            self.result = val
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def _ask_string(parent, title, prompt, initialvalue=""):
    d = _ChineseDialog(parent, title, prompt, initialvalue, "string")
    return d.result


def _ask_integer(parent, title, prompt, initialvalue=0):
    d = _ChineseDialog(parent, title, prompt, str(initialvalue), "integer")
    if d.result is None:
        return None
    try:
        return int(d.result)
    except ValueError:
        return None

if IS_MAC:
    from mac_recorder import MacRecorder as Recorder
    from mac_player import MacPlayer as Player
    from mac_recorder import get_visible_windows
else:
    from recorder import Recorder
    from player import Player
    get_visible_windows = None

from script_manager import ScriptManager

logger = logging.getLogger("gui")

KEYCODE_NAMES = {
    0: "A", 1: "S", 2: "D", 3: "F", 4: "H", 5: "G", 6: "Z", 7: "X",
    8: "C", 9: "V", 11: "B", 12: "Q", 13: "W", 14: "E", 15: "R",
    16: "Y", 17: "T", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6",
    23: "5", 24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0",
    30: "]", 31: "O", 32: "U", 33: "[", 34: "I", 35: "P", 36: "Return",
    37: "L", 38: "J", 39: "'", 40: "K", 41: ";", 42: "\\", 43: ",",
    44: "/", 45: "N", 46: "M", 47: ".", 48: "Tab", 49: "Space",
    50: "`", 51: "Backspace", 53: "Esc", 55: "Cmd", 56: "Shift",
    57: "CapsLock", 58: "Option", 59: "Ctrl", 122: "F1", 123: "F2",
    124: "F3", 125: "F4", 126: "F5", 127: "F6",
}


def _human_key_name(keycode, modifiers=None, text=""):
    if text and len(text) == 1:
        parts = []
        if modifiers:
            mod_map = {"cmd": "\u2318", "shift": "\u21e7", "ctrl": "\u2303", "alt": "\u2325"}
            parts = [mod_map.get(m, m) for m in modifiers]
        parts.append(text.upper() if not modifiers else text)
        return "+".join(parts)
    name = KEYCODE_NAMES.get(keycode, f"Key{keycode}")
    parts = []
    if modifiers:
        mod_map = {"cmd": "\u2318", "shift": "\u21e7", "ctrl": "\u2303", "alt": "\u2325"}
        parts = [mod_map.get(m, m) for m in modifiers]
    parts.append(name)
    return "+".join(parts)


def _human_event_detail(e, scripts_dir=""):
    etype = e.get("type", "")
    if etype == "mouse_down":
        btn_map = {"left": "左键", "right": "右键", "other": "中键"}
        btn = btn_map.get(e.get("button", "left"), "左键")
        parts = [f"点击({btn})"]
        ax = e.get("ax_element")
        if ax:
            role = ax.get("AXRoleDescription", ax.get("AXRole", ""))
            title = ax.get("AXTitle", "")
            desc = ax.get("AXDescription", "")
            if title:
                parts.append(f"「{title}」{role}")
            elif desc:
                parts.append(f"「{desc}」{role}")
            elif role:
                parts.append(role)
        anchor = e.get("ocr_anchor")
        if anchor and anchor.get("text"):
            parts.append(f"附近文字:「{anchor['text']}」")
        tpl = e.get("template")
        if tpl and scripts_dir:
            tpl_path = os.path.join(scripts_dir, "templates", tpl)
            if os.path.exists(tpl_path):
                parts.append("📸有截图")
        var = e.get("variable", "")
        if var:
            parts.append(f"🔗变量:{var}")
        return " ".join(parts)
    elif etype == "mouse_up":
        return ""
    elif etype == "mouse_drag":
        return f"拖拽到 ({e.get('x', 0):.0f}, {e.get('y', 0):.0f})"
    elif etype == "scroll":
        dy = e.get("dy", 0)
        direction = "向下" if dy < 0 else "向上" if dy > 0 else ""
        return f"滚动{direction}"
    elif etype == "key_down":
        text = e.get("text", "")
        mods = e.get("modifiers", [])
        return f"按键 {_human_key_name(e.get('keycode', 0), mods, text)}"
    elif etype == "key_up":
        return ""
    elif etype == "type_text":
        var = e.get("variable", "")
        text = e.get("text", "")
        if var:
            return f"输入变量「{var}」→ {text}"
        return f"输入文字「{text}」"
    elif etype == "screenshot":
        return "📸 自动截图"
    elif etype == "wait_for":
        return f"等待 {e.get('strategy', 'template')} 超时={e.get('timeout', 10)}s"
    elif etype == "assert_that":
        return f"断言 {e.get('description', '')}"
    elif etype == "activate":
        return "激活窗口"
    elif etype == "if":
        return f"如果 {e.get('strategy', 'template')} 满足"
    elif etype == "endif":
        return "结束条件"
    elif etype == "for":
        return f"循环 {e.get('count', 1)} 次"
    elif etype == "endfor":
        return "结束循环"
    elif etype == "while":
        return f"当 {e.get('strategy', 'template')} 满足时循环"
    elif etype == "endwhile":
        return "结束While"
    elif etype == "set_variable":
        return f"设变量 {e.get('name', '')} = {e.get('value', '')}"
    elif etype == "call_script":
        return f"调用脚本「{e.get('script_name', '')}」"
    elif etype == "comment":
        return f"💬 {e.get('text', '')}"
    elif etype == "ai_recognize":
        target = e.get("target", "验证码")
        var = e.get("variable", "")
        return f"🤖 AI识别{target}" + (f" → {var}" if var else "")
    elif etype == "wait_manual":
        return f"⏸ 等待人工: {e.get('description', '请手动操作后继续')}"
    return etype


class AutoRepeatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GhostAction")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        self.recorder = None
        self.player = None
        self.sm = ScriptManager()
        self.recording = False
        self.playing = False
        self.record_start_time = None
        self._hotkey_tap = None
        self._hotkey_run_loop = None
        self._window_list = []
        self._current_script_name = None
        self._current_events = []
        self._scripts_dir = os.path.join(os.path.expanduser("~"), "GhostAction")
        self._pid_name_map = {}

        self._build_ui()
        self._refresh_scripts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(3000, self._check_update)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 8))

        self.btn_record = ttk.Button(ctrl, text="● 识别", command=self._toggle_record, width=12)
        self.btn_record.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_play = ttk.Button(ctrl, text="▶ 复现", command=self._play, width=12)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = ttk.Button(ctrl, text="⏸ 暂停", command=self._toggle_pause, width=8, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_stop_play = ttk.Button(ctrl, text="⏹ 停止", command=self._stop_play, width=8, state=tk.DISABLED)
        self.btn_stop_play.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Separator(ctrl, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.btn_new = ttk.Button(ctrl, text="➕新建", command=self._new_script, width=8)
        self.btn_new.pack(side=tk.LEFT, padx=(0, 6))

        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Label(ctrl, text="速度:").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Spinbox(ctrl, from_=0.25, to=5.0, increment=0.25, textvariable=self.speed_var, width=5).pack(side=tk.LEFT)

        row2 = ttk.Frame(main)
        row2.pack(fill=tk.X, pady=(0, 4))

        self.status_var = tk.StringVar(value="就绪 | ⌃⇧R 识别 | ⌃⇧S 停止")
        ttk.Label(row2, textvariable=self.status_var, foreground="#555").pack(side=tk.LEFT)

        self.count_var = tk.StringVar(value="")
        ttk.Label(row2, textvariable=self.count_var, foreground="#999").pack(side=tk.RIGHT)

        self.version_var = tk.StringVar(value=f"GhostAction v{mp.CURRENT_VERSION}")
        version_label = ttk.Label(row2, textvariable=self.version_var, foreground="#999", cursor="hand2")
        version_label.pack(side=tk.RIGHT, padx=(0, 12))
        version_label.bind("<Button-1>", lambda e: self._check_update_manual())

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)

        scripts_tab = ttk.Frame(nb)
        nb.add(scripts_tab, text=" 脚本列表 ")

        cols = ("name", "events", "created")
        self.tree = ttk.Treeview(scripts_tab, columns=cols, show="headings", height=8)
        self.tree.heading("name", text="脚本名")
        self.tree.heading("events", text="步骤数")
        self.tree.heading("created", text="创建时间")
        self.tree.column("name", width=250)
        self.tree.column("events", width=80)
        self.tree.column("created", width=180)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(scripts_tab, orient=tk.VERTICAL, command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

        btn_frame = ttk.Frame(scripts_tab)
        btn_frame.pack(fill=tk.X, pady=(3, 0))
        ttk.Button(btn_frame, text="编辑", command=self._open_editor, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="重命名", command=self._rename, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="删除", command=self._delete, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="刷新", command=self._refresh_scripts, width=8).pack(side=tk.LEFT, padx=3)


        self.editor_tab = ttk.Frame(nb)
        nb.add(self.editor_tab, text=" 编辑 ")

        self.market_tab = ttk.Frame(nb)
        nb.add(self.market_tab, text=" 🏪 市场 ")

        self._build_editor()
        self._build_marketplace()
        self._start_hotkey_listener()
        self._pump_ns_runloop()

    def _build_editor(self):
        for w in self.editor_tab.winfo_children():
            w.destroy()

        top_frame = ttk.Frame(self.editor_tab)
        top_frame.pack(fill=tk.X, pady=(0, 4))
        self.editor_title_var = tk.StringVar(value="未加载脚本")
        ttk.Label(top_frame, textvariable=self.editor_title_var, font=("", 11, "bold")).pack(side=tk.LEFT)

        filter_frame = ttk.Frame(self.editor_tab)
        filter_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(filter_frame, text="只保留窗口:").pack(side=tk.LEFT, padx=(0, 4))
        self.filter_window_var = tk.StringVar(value="全部")
        self.filter_window_combo = ttk.Combobox(filter_frame, textvariable=self.filter_window_var, width=40, state="readonly")
        self.filter_window_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.filter_window_combo.bind("<<ComboboxSelected>>", self._apply_window_filter)
        ttk.Button(filter_frame, text="合并连续点击", command=self._merge_clicks, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(filter_frame, text="去除截图", command=self._remove_screenshots, width=10).pack(side=tk.LEFT, padx=4)

        btn_row1 = ttk.Frame(self.editor_tab)
        btn_row1.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(btn_row1, text="禁用/启用", command=self._editor_toggle_disable, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="删除", command=self._editor_delete_step, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="↑", command=lambda: self._editor_move(-1), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="↓", command=lambda: self._editor_move(1), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Separator(btn_row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(btn_row1, text="等待", command=self._editor_insert_wait, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="断言", command=self._editor_insert_assert, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="循环", command=self._editor_insert_for, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="注释", command=self._editor_insert_comment, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row1, text="💾保存", command=self._editor_save, width=6).pack(side=tk.RIGHT, padx=2)

        btn_row2 = ttk.Frame(self.editor_tab)
        btn_row2.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_row2, text="➕点选添加", command=self._editor_pick_element, width=9).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="🔗变量", command=self._editor_bind_variable, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="📊数据源", command=self._editor_set_data_source, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="🤖AI识别", command=self._editor_insert_ai_recognize, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="⚙️AI设置", command=self._show_ai_settings, width=8).pack(side=tk.LEFT, padx=2)

        tree_frame = ttk.Frame(self.editor_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("idx", "icon", "detail", "window", "disabled")
        self.editor_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        self.editor_tree.heading("idx", text="#")
        self.editor_tree.heading("icon", text="")
        self.editor_tree.heading("detail", text="操作描述")
        self.editor_tree.heading("window", text="窗口")
        self.editor_tree.heading("disabled", text="")
        self.editor_tree.column("idx", width=35, minwidth=30)
        self.editor_tree.column("icon", width=30, minwidth=30)
        self.editor_tree.column("detail", width=480, minwidth=200)
        self.editor_tree.column("window", width=150, minwidth=80)
        self.editor_tree.column("disabled", width=30, minwidth=30)
        self.editor_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        esb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.editor_tree.yview)
        esb.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor_tree.configure(yscrollcommand=esb.set)

        self.editor_tree.bind("<<TreeviewSelect>>", self._on_editor_select)
        self.editor_tree.bind("<Double-1>", self._on_editor_double_click)

        bottom_frame = ttk.Frame(self.editor_tab)
        bottom_frame.pack(fill=tk.X, pady=(4, 0))

        self.chain_frame = ttk.LabelFrame(bottom_frame, text="📋 操作逻辑链")
        self.chain_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        self.chain_text = tk.Text(self.chain_frame, height=6, wrap=tk.WORD, font=("", 10), state=tk.DISABLED, background="#f0f0f0", foreground="#1a1a1a", selectbackground="#4a90d9")
        self.chain_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.preview_frame = ttk.LabelFrame(bottom_frame, text="步骤预览")
        self.preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preview_label = ttk.Label(self.preview_frame, text="选择一个步骤查看详情", wraplength=400)
        self.preview_label.pack(padx=4, pady=4, fill=tk.BOTH, expand=True)

    def _toggle_record(self):
        if self.recording:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        name = _ask_string(self.root, "识别", "输入脚本名称:")
        if not name:
            return
        name = name.strip().replace(" ", "_")
        self.current_record_name = name
        ss_dir = os.path.join(self._scripts_dir, "scripts", f"{name}_screenshots")
        try:
            self.recorder = Recorder(screenshot_interval=2.0, screenshot_dir=ss_dir, ocr_anchors=True, visual_templates=True)
            self.recorder.start()
        except RuntimeError as e:
            messagebox.showerror("权限错误", f"{e}\n\n请在 系统设置 > 隐私与安全性 > 辅助功能 中添加 Terminal/Python")
            return
        self.recording = True
        self.record_start_time = time.time()
        self.btn_record.configure(text="■ 停止识别")
        self.btn_play.configure(state=tk.DISABLED)
        self.status_var.set("识别中... | ⌃⇧S 停止")
        self.root.iconify()
        self._update_record_count()

    def _stop_record(self):
        if not self.recorder:
            return
        self.status_var.set("处理中...")
        self.root.update_idletasks()
        events = self.recorder.stop()
        self.recording = False

        pids = [e.get("pid") for e in events if e.get("pid")]
        pid_counter = Counter(pids)
        window_info = {}
        if get_visible_windows:
            for w in get_visible_windows():
                window_info[w["pid"]] = w.get("owner", "")
        pid_names = {}
        for pid, count in pid_counter.most_common():
            pname = window_info.get(pid, f"PID:{pid}")
            pid_names[pid] = pname

        click_count = sum(1 for e in events if e["type"] == "mouse_down")
        key_count = sum(1 for e in events if e["type"] == "key_down")
        drag_count = sum(1 for e in events if e["type"] == "mouse_drag")
        meta = {
            "clicks": click_count, "keys": key_count, "drags": drag_count,
            "duration": round(time.time() - self.record_start_time, 1),
            "pid_names": pid_names,
        }

        logic_chain = self._build_logic_chain(events, pid_names)
        meta["logic_chain"] = logic_chain

        self.sm.save(self.current_record_name, events, meta)
        self.btn_record.configure(text="● 识别")
        self.btn_play.configure(state=tk.NORMAL)
        self.status_var.set(f"识别完成 | {click_count}点击 {key_count}按键 {drag_count}拖拽")
        self.root.deiconify()
        self._refresh_scripts()

        self._current_script_name = self.current_record_name
        self._current_events = events
        self._open_editor_for_script(self.current_record_name)

    def _ocr_click_region(self, events, click_idx):
        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            return ""
        click_e = events[click_idx]
        cx, cy = click_e.get("x", 0), click_e.get("y", 0)
        click_time = click_e.get("time", 0)
        best_ss = None
        best_dt = float("inf")
        for i, e in enumerate(events):
            if e.get("type") != "screenshot":
                continue
            dt = abs(e.get("time", 0) - click_time)
            if dt < best_dt and e.get("file"):
                best_dt = dt
                best_ss = e
        if not best_ss or best_dt > 5:
            return ""
        win = best_ss.get("window", {})
        wx, wy = win.get("x", 0), win.get("y", 0)
        ww, wh = win.get("width", 0), win.get("height", 0)
        if ww <= 0 or wh <= 0:
            return ""
        local_x = cx - wx
        local_y = cy - wy
        if local_x < 0 or local_y < 0 or local_x > ww or local_y > wh:
            return ""
        ss_dir = os.path.join(self._scripts_dir, "scripts", f"{self._current_script_name}_screenshots")
        ss_path = os.path.join(ss_dir, best_ss["file"])
        if not os.path.exists(ss_path):
            return ""
        try:
            img = Image.open(ss_path)
            for margin in [80, 140, 200]:
                left = max(0, int(local_x - margin))
                top = max(0, int(local_y - margin))
                right = min(img.width, int(local_x + margin))
                bottom = min(img.height, int(local_y + margin))
                if right - left < 20 or bottom - top < 20:
                    continue
                region = img.crop((left, top, right, bottom))
                text = pytesseract.image_to_string(region, lang="chi_sim+eng").strip()
                text = " ".join(text.split())[:40]
                if text:
                    return text
            return ""
            return text
        except Exception:
            return ""

    def _build_logic_chain(self, events, pid_names):
        steps = []
        last_pid = None
        last_window = None
        for idx, e in enumerate(events):
            if e["type"] not in ("mouse_down", "key_down", "scroll"):
                continue
            pid = e.get("pid")
            window = e.get("window") or {}
            win_owner = window.get("owner", "") or pid_names.get(pid, "")
            win_title = window.get("title", "")

            if pid and pid != last_pid and win_owner:
                label = win_owner
                if win_title and win_title != win_owner:
                    label += f" - {win_title}"
                steps.append({"type": "switch_window", "target": label, "pid": pid})
                last_pid = pid
                last_window = label

            if e["type"] == "mouse_down":
                btn = e.get("button", "left")
                btn_cn = {"left": "左键", "right": "右键", "middle": "中键"}.get(btn, btn)
                ocr = e.get("ocr_anchor", {})
                ocr_text = ocr.get("text", "") if ocr else ""
                ax = e.get("ax_element", {})
                ax_title = ax.get("AXTitle", "") if ax else ""
                ax_role = ax.get("AXRole", "") if ax else ""
                ax_desc = ax.get("AXDescription", "") if ax else ""
                tpl = e.get("template", "")

                desc_parts = []
                if ocr_text:
                    desc_parts.append(f"「{ocr_text}」")
                if ax_title:
                    desc_parts.append(f"「{ax_title}」")
                elif ax_desc:
                    desc_parts.append(f"「{ax_desc}」")

                role_cn = {"AXButton": "按钮", "AXStaticText": "文本", "AXTextField": "输入框",
                           "AXCheckBox": "复选框", "AXRadioButton": "单选按钮", "AXMenu": "菜单",
                           "AXMenuItem": "菜单项", "AXLink": "链接", "AXTabGroup": "标签页",
                           "AXPopUpButton": "下拉框", "AXTable": "表格", "AXRow": "行",
                           }.get(ax_role, "")

                if role_cn and not desc_parts:
                    desc_parts.append(role_cn)

                if not desc_parts:
                    ss_ocr = self._ocr_click_region(events, idx)
                    if ss_ocr:
                        desc_parts.append(f"「{ss_ocr}」")

                desc = "".join(desc_parts) if desc_parts else f"({e.get('x', 0):.0f},{e.get('y', 0):.0f})"
                step = {
                    "type": "click",
                    "button": btn_cn,
                    "desc": desc,
                    "x": e.get("x", 0), "y": e.get("y", 0),
                    "pid": pid, "window": last_window,
                    "ocr": ocr_text, "ax_title": ax_title, "ax_role": ax_role,
                    "template": tpl,
                }
                if e.get("modifiers"):
                    step["modifiers"] = e["modifiers"]
                steps.append(step)

            elif e["type"] == "key_down":
                text = e.get("text", "")
                keycode = e.get("keycode", 0)
                mods = e.get("modifiers", [])
                if text and text.isprintable() and len(text) == 1:
                    step = {"type": "input", "text": text, "pid": pid, "window": last_window}
                else:
                    key_name = {"cmd": "⌘", "shift": "⇧", "ctrl": "⌃", "alt": "⌥"}
                    mod_str = "".join(key_name.get(m, m) for m in mods)
                    kc_names = {36: "↵", 48: "⌫", 51: "⌦", 49: "空格", 53: "⎋"}
                    kn = kc_names.get(keycode, f"键{keycode}")
                    step = {"type": "keypress", "key": f"{mod_str}{kn}", "pid": pid, "window": last_window}
                steps.append(step)

            elif e["type"] == "scroll":
                dy = e.get("dy", 0)
                direction = "上滚" if dy > 0 else "下滚"
                steps.append({"type": "scroll", "direction": direction, "amount": abs(dy), "pid": pid, "window": last_window})

        return steps

    def _update_record_count(self):
        if not self.recording:
            return
        if self.recorder and self.recorder.should_stop():
            self._stop_record()
            return
        if self.recorder:
            self.recorder._process_raw_events()
        elapsed = time.time() - self.record_start_time if self.record_start_time else 0
        count = len(self.recorder.events) if self.recorder else 0
        self.count_var.set(f"事件: {count} | {elapsed:.1f}s")
        self.root.after(100, self._update_record_count)

    def _play(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个脚本")
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        data = self.sm.load(name)
        if not data:
            messagebox.showerror("错误", f"脚本不存在: {name}")
            return
        events = [e for e in data.get("events", []) if not e.get("disabled")]
        speed = self.speed_var.get()
        pids = [e.get("pid") for e in events if e.get("pid")]
        target_pid = Counter(pids).most_common(1)[0][0] if pids else None
        data_source = data.get("meta", {}).get("data_source")
        has_variables = any(e.get("variable") for e in events)
        if has_variables and not data_source:
            messagebox.showwarning("提示", "脚本包含变量标记，但未绑定数据源。\n请在编辑器中点击「📊数据源」按钮绑定数据文件。")
            return
        self.player = Player(speed=speed, target_pid=target_pid, smart_replay=True,
                             visual_match=True, scripts_dir=self._scripts_dir,
                             retry_count=3, on_error="continue")
        self.playing = True
        self.btn_play.configure(state=tk.DISABLED)
        self.btn_record.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL)
        self.btn_stop_play.configure(state=tk.NORMAL)
        ds_info = data_source if (data_source and has_variables) else None
        if ds_info:
            self.status_var.set(f"数据驱动复现中... | {name} | {ds_info.get('row_count', '?')}行 | {speed}x")
        else:
            self.status_var.set(f"复现中... | {name} | {speed}x")
        self.root.iconify()

        def run():
            self.player.play(events, variables={}, data_source=ds_info)
            self.root.after(0, self._on_play_done, name)

        threading.Thread(target=run, daemon=True).start()

    def _toggle_pause(self):
        if not self.player:
            return
        if self.btn_pause.cget("text") == "⏸ 暂停":
            self.player.pause()
            self.btn_pause.configure(text="▶ 继续")
            self.status_var.set("复现已暂停")
        else:
            self.player.resume()
            self.btn_pause.configure(text="⏸ 暂停")
            self.status_var.set("复现中...")

    def _on_play_done(self, name):
        self.playing = False
        self.btn_play.configure(state=tk.NORMAL)
        self.btn_record.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED, text="⏸ 暂停")
        self.btn_stop_play.configure(state=tk.DISABLED)
        log = self.player.execution_log if self.player else []
        fail_count = sum(1 for l in log if l.get("status") == "fail")
        ok_count = sum(1 for l in log if l.get("status") == "ok")
        self.status_var.set(f"复现完成 | {name} | {ok_count}成功 {fail_count}失败")
        self.root.deiconify()
        if self.player and hasattr(self.player, 'generate_report'):
            report = self.player.generate_report(name)
            report_dir = os.path.join(self._scripts_dir, "reports")
            os.makedirs(report_dir, exist_ok=True)
            import time as _time
            report_path = os.path.join(report_dir, f"{name}_{_time.strftime('%Y%m%d_%H%M%S')}.html")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info("执行报告: %s", report_path)

    def _stop_play(self):
        if self.player:
            self.player.stop()
        self.playing = False
        self.btn_play.configure(state=tk.NORMAL)
        self.btn_record.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED, text="⏸ 暂停")
        self.btn_stop_play.configure(state=tk.DISABLED)
        self.status_var.set("复现已停止")
        self.root.deiconify()

    def _refresh_scripts(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.sm.list_all():
            self.tree.insert("", tk.END, values=(s["name"], s["events"], s["created"]))

    def _rename(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        old_name = item["values"][0]
        new_name = _ask_string(self.root, "重命名", "新名称:", initialvalue=old_name)
        if new_name and new_name != old_name:
            data = self.sm.load(old_name)
            if data:
                data["name"] = new_name
                self.sm.save(new_name, data["events"], data.get("meta"))
                self.sm.delete(old_name)
                self._refresh_scripts()

    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        if messagebox.askyesno("确认", f"删除脚本: {name}?"):
            self.sm.delete(name)
            self._refresh_scripts()

    def _open_editor(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个脚本")
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        self._open_editor_for_script(name)

    def _new_script(self):
        name = _ask_string(self.root, "新建脚本", "脚本名称:")
        if not name:
            return
        name = name.strip().replace(" ", "_")
        existing = self.sm.load(name)
        if existing:
            messagebox.showwarning("提示", f"脚本 '{name}' 已存在")
            self._open_editor_for_script(name)
            return
        self.sm.save(name, [], {"pid_names": {}, "clicks": 0, "keys": 0, "drags": 0, "duration": 0})
        self._current_script_name = name
        self._current_events = []
        self._refresh_scripts()
        self._open_editor_for_script(name)

    def _open_editor_for_script(self, name):
        data = self.sm.load(name)
        if not data:
            messagebox.showerror("错误", f"脚本不存在: {name}")
            return
        self._current_script_name = name
        self._current_events = data.get("events", [])
        self.editor_title_var.set(f"编辑: {name} ({len(self._current_events)} 步)")

        pid_names = data.get("meta", {}).get("pid_names", {})
        if not pid_names and get_visible_windows:
            for w in get_visible_windows():
                for e in self._current_events:
                    if e.get("pid") == w["pid"]:
                        pid_names[w["pid"]] = w.get("owner", "")

        pids = set(e.get("pid") for e in self._current_events if e.get("pid"))
        labels = ["全部"]
        self._pid_name_map = {}
        for pid in sorted(pids):
            pname = pid_names.get(pid, f"PID:{pid}")
            label = f"{pname} (PID:{pid})"
            labels.append(label)
            self._pid_name_map[label] = pid
        self.filter_window_combo["values"] = labels
        self.filter_window_var.set("全部")

        self._populate_editor()
        self._show_logic_chain(data)

        nb = self.root.winfo_children()
        for child in nb:
            if isinstance(child, ttk.Notebook):
                child.select(1)
                break

    def _apply_window_filter(self, event=None):
        selected = self.filter_window_var.get()
        if selected == "全部":
            data = self.sm.load(self._current_script_name)
            self._current_events = data.get("events", []) if data else []
        else:
            target_pid = self._pid_name_map.get(selected)
            data = self.sm.load(self._current_script_name)
            all_events = data.get("events", []) if data else []
            self._current_events = [e for e in all_events if e.get("pid") == target_pid or e.get("type") in ("screenshot",)]
        self._populate_editor()

    def _merge_clicks(self):
        merged = []
        skip_next_up = False
        for i, e in enumerate(self._current_events):
            if skip_next_up and e.get("type") == "mouse_up":
                skip_next_up = False
                continue
            if e.get("type") == "mouse_down" and i + 1 < len(self._current_events):
                next_e = self._current_events[i + 1]
                if next_e.get("type") == "mouse_up":
                    merged.append(e)
                    skip_next_up = True
                    continue
            merged.append(e)
        self._current_events = merged
        self._populate_editor()

    def _remove_screenshots(self):
        self._current_events = [e for e in self._current_events if e.get("type") != "screenshot"]
        self._populate_editor()

    def _show_logic_chain(self, data):
        events = data.get("events", [])
        pid_names = data.get("meta", {}).get("pid_names", {})
        chain = self._build_logic_chain(events, pid_names)
        if not chain:
            self.chain_text.configure(state=tk.NORMAL)
            self.chain_text.delete("1.0", tk.END)
            self.chain_text.insert(tk.END, "暂无操作逻辑")
            self.chain_text.configure(state=tk.DISABLED)
            return

        self.chain_text.configure(state=tk.NORMAL)
        self.chain_text.delete("1.0", tk.END)

        self.chain_text.tag_configure("window_header", foreground="#2563eb", font=("", 10, "bold"))
        self.chain_text.tag_configure("step", foreground="#1a1a1a")
        self.chain_text.tag_configure("switch", foreground="#6b7280")
        self.chain_text.tag_configure("coord", foreground="#9ca3af", font=("", 9))

        self._chain_photos = []

        current_window = None
        step_num = 0
        for s in chain:
            win = s.get("window", "")
            if win and win != current_window:
                if current_window is not None:
                    self.chain_text.insert(tk.END, "\n")
                self.chain_text.insert(tk.END, f"🪟 {win}\n", "window_header")
                current_window = win

            if s["type"] == "switch_window":
                self.chain_text.insert(tk.END, f"  🔄 切换到: {s['target']}\n", "switch")
            elif s["type"] == "click":
                step_num += 1
                mod = ""
                if s.get("modifiers"):
                    key_name = {"cmd": "⌘+", "shift": "⇧+", "ctrl": "⌃+", "alt": "⌥+"}
                    mod = "".join(key_name.get(m, m + "+") for m in s["modifiers"])
                desc = s["desc"]
                has_text = not desc.startswith("(")
                self.chain_text.insert(tk.END, f"  {step_num}. {mod}{s['button']}点击 ", "step")
                if has_text:
                    self.chain_text.insert(tk.END, f"{desc}\n", "step")
                else:
                    tpl = s.get("template", "")
                    tpl_path = os.path.join(self._scripts_dir, "templates", tpl) if tpl else ""
                    if tpl and os.path.exists(tpl_path):
                        try:
                            from PIL import Image, ImageTk
                            img = Image.open(tpl_path)
                            img.thumbnail((32, 32), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            self._chain_photos.append(photo)
                            self.chain_text.image_create(tk.END, image=photo)
                            self.chain_text.insert(tk.END, f"  ", "step")
                        except Exception:
                            pass
                    self.chain_text.insert(tk.END, f"{desc}\n", "coord")
            elif s["type"] == "input":
                step_num += 1
                self.chain_text.insert(tk.END, f"  {step_num}. 输入「{s['text']}」\n", "step")
            elif s["type"] == "keypress":
                step_num += 1
                self.chain_text.insert(tk.END, f"  {step_num}. 按下 {s['key']}\n", "step")
            elif s["type"] == "scroll":
                step_num += 1
                self.chain_text.insert(tk.END, f"  {step_num}. {s['direction']} ×{s['amount']}\n", "step")

        self.chain_text.configure(state=tk.DISABLED)

    def _populate_editor(self):
        for item in self.editor_tree.get_children():
            self.editor_tree.delete(item)

        pid_names = {}
        data = self.sm.load(self._current_script_name)
        if data:
            pid_names = data.get("meta", {}).get("pid_names", {})

        window_groups = {}
        step_num = 0
        for i, e in enumerate(self._current_events):
            etype = e.get("type", "")
            if etype in ("mouse_up", "key_up"):
                continue

            step_num += 1
            detail = _human_event_detail(e, self._scripts_dir)

            icon_map = {
                "mouse_down": "👆", "mouse_drag": "✋", "scroll": "🔄",
                "key_down": "⌨️", "type_text": "⌨️", "screenshot": "📸",
                "wait_for": "⏳", "assert_that": "✅", "activate": "🪟",
                "if": "🔀", "endif": "🔚", "for": "🔁", "endfor": "🔚",
                "while": "🔁", "endwhile": "🔚", "set_variable": "📝",
                "call_script": "📞", "comment": "💬", "ai_recognize": "🤖", "wait_manual": "⏸",
            }
            icon = icon_map.get(etype, "•")

            pid = e.get("pid")
            window_str = ""
            if pid:
                window_str = pid_names.get(pid, f"PID:{pid}")

            disabled = "🚫" if e.get("disabled") else ""

            if window_str not in window_groups:
                window_groups[window_str] = []
            window_groups[window_str].append((step_num, icon, detail, window_str, disabled, i))

        for win_name, items in window_groups.items():
            group_label = f"🪟 {win_name}" if win_name else "🪟 未知窗口"
            group_id = self.editor_tree.insert("", tk.END, values=("", "", group_label, "", ""), open=True)
            for step_num, icon, detail, window_str, disabled, idx in items:
                self.editor_tree.insert(group_id, tk.END, iid=f"evt_{idx}", values=(step_num, icon, detail, window_str, disabled))

    def _on_editor_select(self, event=None):
        sel = self.editor_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("evt_"):
            self.preview_label.configure(text="选择一个步骤查看详情")
            return
        idx = int(iid[4:])

        if idx >= len(self._current_events):
            return

        e = self._current_events[idx]
        parts = []

        etype = e.get("type", "")
        if etype == "mouse_down":
            parts.append(f"坐标: ({e.get('x', 0):.0f}, {e.get('y', 0):.0f})")
            ax = e.get("ax_element")
            if ax:
                parts.append(f"元素: {ax.get('AXRoleDescription', ax.get('AXRole', ''))}")
                if ax.get("AXTitle"):
                    parts.append(f"标题: {ax['AXTitle']}")
                if ax.get("AXDescription"):
                    parts.append(f"描述: {ax['AXDescription']}")
            anchor = e.get("ocr_anchor")
            if anchor:
                parts.append(f"OCR锚点: 「{anchor.get('text', '')}」偏移({anchor.get('offset_x', 0)}, {anchor.get('offset_y', 0)})")
            tpl = e.get("template")
            if tpl:
                tpl_path = os.path.join(self._scripts_dir, "templates", tpl)
                if os.path.exists(tpl_path):
                    parts.append(f"📸 模板截图: {tpl}")
            wb = e.get("window_bounds")
            if wb:
                parts.append(f"窗口: {wb.get('owner', '')} ({wb.get('x', 0)},{wb.get('y', 0)}) {wb.get('w', 0)}x{wb.get('h', 0)}")
        elif etype == "key_down":
            parts.append(f"键码: {e.get('keycode', 0)}")
            if e.get("text"):
                parts.append(f"文字: {e['text']}")
            if e.get("modifiers"):
                parts.append(f"修饰键: {', '.join(e['modifiers'])}")
        elif etype == "scroll":
            parts.append(f"方向: dx={e.get('dx', 0)} dy={e.get('dy', 0)}")

        if e.get("pid"):
            parts.append(f"窗口PID: {e['pid']}")

        self.preview_label.configure(text="\n".join(parts) if parts else "无详细信息")

    def _on_editor_double_click(self, event=None):
        sel = self.editor_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("evt_"):
            return
        idx = int(iid[4:])
        e = self._current_events[idx] if idx < len(self._current_events) else None
        if not e:
            return
        tpl = e.get("template")
        if tpl:
            tpl_path = os.path.join(self._scripts_dir, "templates", tpl)
            if os.path.exists(tpl_path):
                self._show_image_preview(tpl_path)
                return
        ss_dir = os.path.join(self._scripts_dir, "scripts", f"{self._current_script_name}_screenshots")
        for j in range(idx, -1, -1):
            ss = self._current_events[j]
            if ss.get("type") == "screenshot" and ss.get("file"):
                ss_path = os.path.join(ss_dir, ss["file"])
                if os.path.exists(ss_path):
                    self._show_image_preview(ss_path)
                    return

    def _show_image_preview(self, image_path):
        try:
            from PIL import Image, ImageTk
            top = tk.Toplevel(self.root)
            top.title("步骤截图预览")
            img = Image.open(image_path)
            max_w, max_h = 800, 600
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label = ttk.Label(top, image=photo)
            label.image = photo
            label.pack(padx=8, pady=8)
            ttk.Label(top, text=os.path.basename(image_path)).pack(pady=(0, 8))
        except Exception as ex:
            messagebox.showinfo("预览", f"无法显示截图: {ex}")

    def _editor_toggle_disable(self):
        sel = self.editor_tree.selection()
        if not sel:
            return
        for s in sel:
            if not s.startswith("evt_"):
                continue
            idx = int(s[4:])
            if idx < len(self._current_events):
                self._current_events[idx]["disabled"] = not self._current_events[idx].get("disabled", False)
        self._populate_editor()

    def _editor_delete_step(self):
        sel = self.editor_tree.selection()
        if not sel:
            return
        indices = sorted([int(s[4:]) for s in sel if s.startswith("evt_")], reverse=True)
        for idx in indices:
            if idx < len(self._current_events):
                del self._current_events[idx]
                if idx < len(self._current_events) and self._current_events[idx].get("type") == "mouse_up":
                    del self._current_events[idx]
        self._populate_editor()

    def _editor_move(self, direction):
        sel = self.editor_tree.selection()
        if not sel or len(sel) != 1:
            return
        if not sel[0].startswith("evt_"):
            return
        idx = int(sel[0][4:])
        new_i = idx + direction
        if new_i < 0 or new_i >= len(self._current_events):
            return
        self._current_events[idx], self._current_events[new_i] = self._current_events[new_i], self._current_events[idx]
        self._populate_editor()

    def _get_selected_event_idx(self):
        sel = self.editor_tree.selection()
        if not sel or not sel[0].startswith("evt_"):
            return len(self._current_events)
        return int(sel[0][4:]) + 1

    def _editor_insert_wait(self):
        idx = self._get_selected_event_idx()
        timeout = _ask_integer(self.root, "等待", "等待秒数:", initialvalue=3) or 3
        ev = {"type": "wait_for", "strategy": "template", "timeout": timeout, "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_assert(self):
        idx = self._get_selected_event_idx()
        desc = _ask_string(self.root, "断言", "断言描述:") or ""
        ev = {"type": "assert_that", "strategy": "template", "description": desc, "timeout": 5, "on_fail": "warn", "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_for(self):
        idx = self._get_selected_event_idx()
        n = _ask_integer(self.root, "循环", "循环次数:", initialvalue=3) or 3
        ev_for = {"type": "for", "count": n, "variable": "_i", "time": 0}
        ev_endfor = {"type": "endfor", "time": 0}
        self._current_events.insert(idx, ev_for)
        self._current_events.insert(idx + 1, ev_endfor)
        self._populate_editor()

    def _editor_insert_comment(self):
        idx = self._get_selected_event_idx()
        text = _ask_string(self.root, "注释", "注释内容:") or ""
        ev = {"type": "comment", "text": text, "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_ai_recognize(self):
        if not self._current_script_name:
            self._new_script()
            if not self._current_script_name:
                return

        top = tk.Toplevel(self.root)
        top.title("🤖 添加AI识别步骤")
        top.geometry("450x350")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="AI识别步骤：截图指定区域→调用大模型识别→结果存入变量", font=("", 10, "bold"), wraplength=420).pack(anchor="w", pady=(0, 8))

        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="识别目标:").pack(side=tk.LEFT, padx=(0, 4))
        target_var = tk.StringVar(value="验证码")
        ttk.Combobox(row1, textvariable=target_var, values=["验证码", "文字", "数字", "图形"], width=12, state="readonly").pack(side=tk.LEFT)

        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="结果存入变量:").pack(side=tk.LEFT, padx=(0, 4))
        var_name = tk.StringVar(value="captcha_result")
        ttk.Entry(row2, textvariable=var_name, width=20).pack(side=tk.LEFT)

        row3 = ttk.Frame(frm)
        row3.pack(fill=tk.X, pady=4)
        ttk.Label(row3, text="识别区域:").pack(side=tk.LEFT, padx=(0, 4))
        region_var = tk.StringVar(value="自动截图")
        region_combo = ttk.Combobox(row3, textvariable=region_var, values=["自动截图", "手动指定区域"], width=15, state="readonly")
        region_combo.pack(side=tk.LEFT)

        row4 = ttk.Frame(frm)
        row4.pack(fill=tk.X, pady=4)
        ttk.Label(row4, text="自定义提示词:").pack(side=tk.LEFT, padx=(0, 4))
        prompt_var = tk.StringVar(value="")
        prompt_entry = ttk.Entry(row4, textvariable=prompt_var, width=30)
        prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row5 = ttk.Frame(frm)
        row5.pack(fill=tk.X, pady=4)
        manual_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row5, text="AI失败时回退到人工接管", variable=manual_var).pack(anchor="w")

        def _confirm():
            idx = self._get_selected_event_idx()
            target = target_var.get()
            var = var_name.get().strip()
            if not var:
                messagebox.showwarning("提示", "请输入变量名", parent=top)
                return
            prompt = prompt_var.get().strip() or f"请识别图中的{target}，只输出{target}内容，不要输出其他文字"
            ev = {
                "type": "ai_recognize",
                "target": target,
                "variable": var,
                "prompt": prompt,
                "region": region_var.get(),
                "fallback_manual": manual_var.get(),
                "time": 0,
            }
            self._current_events.insert(idx, ev)
            if manual_var.get():
                wait_ev = {
                    "type": "wait_manual",
                    "description": f"如果AI识别{target}失败，请手动输入后点击继续",
                    "variable": var,
                    "time": 0,
                }
                self._current_events.insert(idx + 1, wait_ev)
            self._populate_editor()
            self.status_var.set(f"已添加AI识别步骤: {target} → {var}")
            top.destroy()

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="添加", command=_confirm, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _show_ai_settings(self):
        import ai_recognizer as ai
        config = ai.load_config()

        top = tk.Toplevel(self.root)
        top.title("⚙️ AI模型设置")
        top.geometry("600x650")
        top.transient(self.root)
        top.grab_set()

        canvas = tk.Canvas(top)
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding=12)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        frm = scroll_frame

        ttk.Label(frm, text="配置大模型API Key，用于验证码识别等AI功能", font=("", 10, "bold"), wraplength=550).pack(anchor="w", pady=(0, 4))
        ttk.Label(frm, text="默认搭载免费模型，配置Key即可使用；可升级付费模型", foreground="#666").pack(anchor="w", pady=(0, 8))

        providers = config.get("providers", {})
        key_entries = {}
        all_providers = list(ai.PROVIDER_CONFIG.keys())

        for provider_key in all_providers:
            pinfo = ai.PROVIDER_CONFIG[provider_key]
            pf = ttk.LabelFrame(frm, text=pinfo["name"], padding=4)
            pf.pack(fill=tk.X, pady=2)

            kf = ttk.Frame(pf)
            kf.pack(fill=tk.X)
            ttk.Label(kf, text="API Key:").pack(side=tk.LEFT, padx=(0, 4))
            key_var = tk.StringVar(value=providers.get(provider_key, {}).get("api_key", ""))
            entry = ttk.Entry(kf, textvariable=key_var, width=35, show="*")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            key_entries[provider_key] = key_var

            show_var = tk.BooleanVar(value=False)
            def _toggle(e=entry, sv=show_var):
                e.configure(show="" if sv.get() else "*")
            ttk.Checkbutton(kf, text="显示", variable=show_var, command=_toggle).pack(side=tk.LEFT, padx=4)

            enabled_var = tk.BooleanVar(value=providers.get(provider_key, {}).get("enabled", True))
            ttk.Checkbutton(pf, text="启用", variable=enabled_var).pack(side=tk.LEFT)
            key_entries[f"{provider_key}_enabled"] = enabled_var

            models_for_provider = [f"  {v['name']} ({'免费' if v['free'] else '付费'}) - {v['description']}" for k, v in ai.MODEL_REGISTRY.items() if v["provider"] == provider_key]
            if models_for_provider:
                ttk.Label(pf, text="\n".join(models_for_provider), foreground="#888", font=("", 8), wraplength=500, justify=tk.LEFT).pack(anchor="w", pady=(2, 0))

        model_frame = ttk.LabelFrame(frm, text="默认模型选择", padding=6)
        model_frame.pack(fill=tk.X, pady=4)

        vmf = ttk.Frame(model_frame)
        vmf.pack(fill=tk.X, pady=2)
        ttk.Label(vmf, text="🤖 图形识别模型:").pack(side=tk.LEFT, padx=(0, 4))
        vision_models = [k for k, v in ai.MODEL_REGISTRY.items() if "vision" in v["capabilities"]]
        vision_var = tk.StringVar(value=config.get("vision_model", "glm-4v-flash"))
        ttk.Combobox(vmf, textvariable=vision_var, values=vision_models, width=22, state="readonly").pack(side=tk.LEFT)

        tmf = ttk.Frame(model_frame)
        tmf.pack(fill=tk.X, pady=2)
        ttk.Label(tmf, text="📝 文本推理模型:").pack(side=tk.LEFT, padx=(0, 4))
        text_models = [k for k, v in ai.MODEL_REGISTRY.items() if "text" in v["capabilities"]]
        text_var = tk.StringVar(value=config.get("text_model", "deepseek-chat"))
        ttk.Combobox(tmf, textvariable=text_var, values=text_models, width=22, state="readonly").pack(side=tk.LEFT)

        status_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=status_var, foreground="#2563eb").pack(anchor="w", pady=4)

        def _test():
            model_key = vision_var.get()
            model_info = ai.MODEL_REGISTRY.get(model_key)
            if not model_info:
                status_var.set("❌ 未知模型")
                return
            provider = model_info["provider"]
            api_key = key_entries.get(provider, tk.StringVar()).get()
            ok, msg = ai.test_connection(model_key, api_key)
            status_var.set(f"{'✅' if ok else '❌'} {msg}")

        def _save():
            for provider_key in all_providers:
                if provider_key not in config["providers"]:
                    config["providers"][provider_key] = {}
                config["providers"][provider_key]["api_key"] = key_entries[provider_key].get()
                config["providers"][provider_key]["enabled"] = key_entries[f"{provider_key}_enabled"].get()
            config["vision_model"] = vision_var.get()
            config["text_model"] = text_var.get()
            ai.save_config(config)
            status_var.set("✅ 设置已保存")
            self.status_var.set("AI设置已保存")

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="测试连接", command=_test, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="保存", command=_save, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="关闭", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _editor_pick_element(self):
        if not self._current_script_name:
            self._new_script()
            if not self._current_script_name:
                return
        self.status_var.set("🎯 点选模式：点击屏幕上的目标元素，按 Esc 取消...")
        self.root.iconify()
        self.root.update_idletasks()
        import time as _time
        _time.sleep(0.3)
        self._pick_tap = None
        self._pick_run_loop = None
        try:
            from Quartz import (
                CGEventTapCreate, CGEventTapEnable,
                kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
                kCGEventLeftMouseDown, kCGEventKeyDown,
                CGEventGetLocation, CGEventGetIntegerValueField,
                kCGKeyboardEventKeycode, CGEventSetType,
                CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
                kCFRunLoopDefaultMode,
            )
            from Foundation import NSRunLoop, NSDate

            def pick_callback(proxy, event_type, event, refcon):
                if event_type == kCGEventKeyDown:
                    kc = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                    if kc == 53:
                        self.root.after(0, self._cancel_pick)
                        return event
                if event_type == kCGEventLeftMouseDown:
                    loc = CGEventGetLocation(event)
                    x, y = loc.x, loc.y
                    self.root.after(0, self._on_pick_click, x, y)
                    return None
                return event

            self._pick_tap = CGEventTapCreate(
                kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
                (1 << kCGEventLeftMouseDown) | (1 << kCGEventKeyDown),
                pick_callback, None,
            )
            if not self._pick_tap:
                self.root.deiconify()
                messagebox.showerror("错误", "无法启动点选模式，请检查辅助功能权限")
                return
            CGEventTapEnable(self._pick_tap, True)
            source = CFMachPortCreateRunLoopSource(None, self._pick_tap, 0)
            rl = NSRunLoop.currentRunLoop().getCFRunLoop()
            CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)
            self._pick_run_loop = rl
            self._pick_source = source
        except Exception as e:
            self.root.deiconify()
            messagebox.showerror("错误", f"点选模式启动失败: {e}")
            return

    def _cancel_pick(self):
        self._cleanup_pick()
        self.root.deiconify()
        self.status_var.set("点选模式已取消")

    def _cleanup_pick(self):
        try:
            if self._pick_tap:
                from Quartz import CGEventTapEnable
                CGEventTapEnable(self._pick_tap, False)
                self._pick_tap = None
        except Exception:
            pass
        try:
            if self._pick_run_loop and self._pick_source:
                from Quartz import CFRunLoopRemoveSource, kCFRunLoopDefaultMode
                CFRunLoopRemoveSource(self._pick_run_loop, self._pick_source, kCFRunLoopDefaultMode)
        except Exception:
            pass

    def _on_pick_click(self, x, y):
        self._cleanup_pick()
        self.root.deiconify()
        self.root.update_idletasks()
        import time as _time
        _time.sleep(0.1)

        pid = None
        window_owner = ""
        window_title = ""
        window_bounds = {}
        try:
            from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            wl = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            for w in wl:
                bounds = w.get('kCGWindowBounds', {})
                bx, by = bounds.get('X', 0), bounds.get('Y', 0)
                bw, bh = bounds.get('Width', 0), bounds.get('Height', 0)
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    layer = w.get('kCGWindowLayer', -1)
                    if layer == 0:
                        pid = w.get('kCGWindowOwnerPID', -1)
                        window_owner = w.get('kCGWindowOwnerName', '')
                        window_title = w.get('kCGWindowName', '')
                        window_bounds = {"x": bx, "y": by, "width": bw, "height": bh, "owner": window_owner}
                        break
        except Exception:
            pass

        ax_element = None
        ax_actions = []
        if pid and pid > 0:
            try:
                from accessibility import get_element_at_point, get_element_attrs, get_element_actions as get_actions
                elem = get_element_at_point(pid, x, y)
                if elem:
                    ax_element = get_element_attrs(elem)
                    ax_actions = get_actions(elem)
            except Exception:
                pass

        ocr_results = []
        try:
            from mac_recorder import ocr_at_point
            ocr_results = ocr_at_point(x, y)
        except Exception:
            pass

        ocr_anchor = None
        if ocr_results:
            best = min(ocr_results, key=lambda r: abs(r["offset_x"]) + abs(r["offset_y"]))
            if len(best["text"]) >= 2:
                ocr_anchor = {
                    "text": best["text"],
                    "offset_x": best["offset_x"],
                    "offset_y": best["offset_y"],
                }

        template_file = None
        tpl_dir = os.path.join(self._scripts_dir, "scripts", "templates")
        try:
            from mac_recorder import capture_template
            idx = len(self._current_events)
            template_file = capture_template(x, y, save_dir=tpl_dir, index=idx)
        except Exception:
            pass

        self._show_pick_dialog(x, y, pid, window_owner, window_title, window_bounds,
                               ax_element, ax_actions, ocr_anchor, template_file)

    def _show_pick_dialog(self, x, y, pid, window_owner, window_title, window_bounds,
                          ax_element, ax_actions, ocr_anchor, template_file):
        top = tk.Toplevel(self.root)
        top.title("🎯 添加步骤")
        top.geometry("500x450")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        info_parts = [f"📍 坐标: ({x:.0f}, {y:.0f})"]
        if window_owner:
            info_parts.append(f"🪟 窗口: {window_owner}")
        if ax_element:
            role = ax_element.get("AXRoleDescription", ax_element.get("AXRole", ""))
            title = ax_element.get("AXTitle", "")
            desc = ax_element.get("AXDescription", "")
            val = ax_element.get("AXValue", "")
            if role:
                info_parts.append(f"🔧 元素: {role}")
            if title:
                info_parts.append(f"📌 标题: {title}")
            elif desc:
                info_parts.append(f"📌 描述: {desc}")
            if val:
                info_parts.append(f"📝 值: {val[:50]}")
        if ocr_anchor:
            info_parts.append(f"🔍 OCR: 「{ocr_anchor['text']}」")

        ttk.Label(frm, text="\n".join(info_parts), font=("", 10), wraplength=460, justify=tk.LEFT).pack(anchor="w", pady=(0, 8))

        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        ttk.Label(frm, text="选择动作:", font=("", 10, "bold")).pack(anchor="w", pady=(4, 4))

        action_var = tk.StringVar(value="click")
        actions_frame = ttk.Frame(frm)
        actions_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Radiobutton(actions_frame, text="👆 点击", variable=action_var, value="click").pack(anchor="w", pady=2)
        ttk.Radiobutton(actions_frame, text="⌨️ 输入文字", variable=action_var, value="type").pack(anchor="w", pady=2)
        ttk.Radiobutton(actions_frame, text="⌨️ 输入变量 {{变量名}}", variable=action_var, value="type_var").pack(anchor="w", pady=2)
        if ax_actions and "AXPress" in ax_actions:
            ttk.Radiobutton(actions_frame, text="🔘 Accessibility点击 (AXPress)", variable=action_var, value="ax_press").pack(anchor="w", pady=2)

        input_frame = ttk.Frame(frm)
        input_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(input_frame, text="输入内容/变量名:").pack(side=tk.LEFT, padx=(0, 4))
        input_var = tk.StringVar()
        input_entry = ttk.Entry(input_frame, textvariable=input_var, width=25)
        input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if ax_element:
            val = ax_element.get("AXValue", "")
            if val:
                input_var.set(val[:30])

        def _confirm_add():
            action = action_var.get()
            idx = self._get_selected_event_idx()
            ev = {"time": 0, "pid": pid}

            if window_owner:
                ev["window"] = {"owner": window_owner, "title": window_title}
            if window_bounds:
                ev["window_bounds"] = window_bounds
            if ocr_anchor:
                ev["ocr_anchor"] = ocr_anchor
            if template_file:
                ev["template"] = template_file

            if action == "click":
                ev["type"] = "mouse_down"
                ev["x"] = x
                ev["y"] = y
                ev["button"] = "left"
                self._current_events.insert(idx, ev)
                up_ev = {"type": "mouse_up", "x": x, "y": y, "button": "left", "time": 0}
                self._current_events.insert(idx + 1, up_ev)

            elif action == "type":
                text = input_var.get()
                if not text:
                    messagebox.showwarning("提示", "请输入内容", parent=top)
                    return
                ev["type"] = "type_text"
                ev["text"] = text
                self._current_events.insert(idx, ev)

            elif action == "type_var":
                var_name = input_var.get().strip()
                if not var_name:
                    messagebox.showwarning("提示", "请输入变量名", parent=top)
                    return
                ev["type"] = "type_text"
                ev["text"] = "{{" + var_name + "}}"
                ev["variable"] = var_name
                self._current_events.insert(idx, ev)

            elif action == "ax_press":
                ev["type"] = "mouse_down"
                ev["x"] = x
                ev["y"] = y
                ev["button"] = "left"
                if ax_element:
                    ev["ax_element"] = ax_element
                    ev["ax_actions"] = ax_actions
                self._current_events.insert(idx, ev)
                up_ev = {"type": "mouse_up", "x": x, "y": y, "button": "left", "time": 0}
                self._current_events.insert(idx + 1, up_ev)

            self._populate_editor()
            self.status_var.set(f"已添加步骤: {action} at ({x:.0f},{y:.0f})")
            top.destroy()

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="添加", command=_confirm_add, width=10).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=top.destroy, width=8).pack(side=tk.RIGHT)

        top.bind("<Escape>", lambda e: top.destroy())

    def _editor_bind_variable(self):
        sel = self.editor_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个步骤")
            return
        iid = sel[0]
        if not iid.startswith("evt_"):
            messagebox.showwarning("提示", "请选择一个具体步骤，不是分组")
            return
        idx = int(iid[4:])
        if idx >= len(self._current_events):
            return
        e = self._current_events[idx]
        etype = e.get("type", "")

        if etype == "type_text":
            current_text = e.get("text", "")
            current_var = e.get("variable", "")
            initial = current_var if current_var else ""
            var_name = _ask_string(self.root, "绑定变量", f"输入变量名（输入内容「{current_text}」将替换为 {{变量名}}）:", initialvalue=initial)
            if var_name:
                e["variable"] = var_name
                if not current_text or not current_text.startswith("{{"):
                    e["text"] = "{{" + var_name + "}}"
                self._populate_editor()
                self.status_var.set(f"已绑定变量: {var_name}")
            return

        if etype == "key_down":
            text = e.get("text", "")
            if text and len(text) > 1:
                current_var = e.get("variable", "")
                initial = current_var if current_var else ""
                var_name = _ask_string(self.root, "绑定变量", f"输入变量名（输入内容「{text}」将替换为 {{变量名}}）:", initialvalue=initial)
                if var_name:
                    e["variable"] = var_name
                    e["type"] = "type_text"
                    e["text"] = "{{" + var_name + "}}"
                    self._populate_editor()
                    self.status_var.set(f"已绑定变量: {var_name}")
                return

        if etype == "mouse_down":
            current_var = e.get("variable", "")
            initial = current_var if current_var else ""
            var_name = _ask_string(self.root, "绑定变量", "为点击步骤绑定变量名（用于数据驱动回放时标记）:", initialvalue=initial)
            if var_name:
                e["variable"] = var_name
                self._populate_editor()
                self.status_var.set(f"已绑定变量: {var_name}")
            return

        messagebox.showinfo("提示", "请选择输入文字、按键或点击步骤来绑定变量")

    def _editor_set_data_source(self):
        from tkinter import filedialog
        filetypes = [
            ("数据文件", "*.csv *.xlsx *.xls *.json"),
            ("CSV文件", "*.csv"),
            ("Excel文件", "*.xlsx *.xls"),
            ("JSON文件", "*.json"),
        ]
        path = filedialog.askopenfilename(title="选择数据源文件", filetypes=filetypes)
        if not path:
            return

        import data_source as ds
        rows = ds.read_file(path)
        if not rows:
            messagebox.showerror("错误", f"无法读取数据文件，或文件为空:\n{path}")
            return

        columns = ds.get_columns(rows)

        preview_lines = [f"文件: {os.path.basename(path)}", f"行数: {len(rows)}", f"列: {', '.join(columns)}", ""]
        for i, row in enumerate(rows[:5]):
            preview_lines.append(f"第{i+1}行: {dict(list(row.items())[:5])}")
        if len(rows) > 5:
            preview_lines.append(f"... 共{len(rows)}行")

        top = tk.Toplevel(self.root)
        top.title("数据源预览")
        top.geometry("600x400")
        top.transient(self.root)

        frm = ttk.Frame(top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=f"📊 数据源: {os.path.basename(path)}", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(frm, text=f"{len(rows)} 行 × {len(columns)} 列").pack(anchor="w", pady=(0, 8))

        cols_display = ("col_name",)
        preview_tree = ttk.Treeview(frm, columns=("index",) + tuple(columns), show="headings", height=8)
        preview_tree.heading("index", text="#")
        preview_tree.column("index", width=40)
        for col in columns:
            preview_tree.heading(col, text=col)
            preview_tree.column(col, width=100, minwidth=60)
        preview_tree.pack(fill=tk.BOTH, expand=True)

        psb = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=preview_tree.yview)
        preview_tree.configure(yscrollcommand=psb.set)

        for i, row in enumerate(rows[:50]):
            vals = [i + 1] + [row.get(c, "") for c in columns]
            preview_tree.insert("", tk.END, values=vals)

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))

        col_var = tk.StringVar()
        ttk.Label(btn_frm, text="主键列:").pack(side=tk.LEFT, padx=(0, 4))
        col_combo = ttk.Combobox(btn_frm, textvariable=col_var, values=columns, state="readonly", width=15)
        col_combo.pack(side=tk.LEFT, padx=(0, 8))
        if columns:
            col_combo.current(0)

        def _confirm():
            data = self.sm.load(self._current_script_name)
            if not data:
                return
            meta = data.get("meta", {})
            meta["data_source"] = {
                "path": path,
                "columns": columns,
                "row_count": len(rows),
                "key_column": col_var.get() or columns[0] if columns else "",
            }
            self.sm.save(self._current_script_name, data.get("events", []), meta)
            self.status_var.set(f"数据源已绑定: {os.path.basename(path)} ({len(rows)}行)")
            top.destroy()

        ttk.Button(btn_frm, text="确认绑定", command=_confirm, width=10).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _editor_save(self):
        if not self._current_script_name:
            messagebox.showwarning("提示", "请先加载脚本")
            return
        data = self.sm.load(self._current_script_name)
        if data:
            data["events"] = self._current_events
            data["event_count"] = len(self._current_events)
            self.sm.save(self._current_script_name, self._current_events, data.get("meta"))
            self.status_var.set(f"已保存: {self._current_script_name}")
            self._refresh_scripts()

    def _check_permissions(self):
        if not IS_MAC:
            return True
        issues = []
        try:
            from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions
            ax = AXIsProcessTrusted()
            logger.info("辅助功能权限: %s", ax)
            if not ax:
                if not getattr(self.__class__, '_ax_prompted', False):
                    self.__class__.__ax_prompted = True
                    AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
                issues.append("辅助功能")
        except Exception as e:
            logger.warning("辅助功能权限检查异常: %s", e)
            issues.append("辅助功能")
        try:
            import mss
            from PIL import Image
            import numpy as np
            with mss.MSS() as sct:
                screenshot = sct.grab(sct.monitors[1])
                im = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                arr = np.array(im)
                std = float(np.std(arr))
            has_screen = std > 10
            logger.info("屏幕录制权限: %s (std=%.1f)", has_screen, std)
            if not has_screen:
                issues.append("屏幕录制")
        except Exception as e:
            logger.warning("屏幕录制权限检查异常: %s", e)
            issues.append("屏幕录制")
        if issues:
            msg = "、".join(issues)
            self.status_var.set(f"⚠ 缺少{msg}权限，请在系统设置中启用")
            logger.warning("缺少权限: %s", msg)
            return False
        return True

    def _start_hotkey_listener(self):
        if not IS_MAC:
            return
        if not self._check_permissions():
            return
        try:
            from Quartz import (
                CGEventTapCreate, CGEventTapEnable,
                kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
                kCGEventKeyDown, kCGEventFlagMaskControl, kCGEventFlagMaskShift,
                CGEventGetFlags, CGEventGetIntegerValueField, kCGKeyboardEventKeycode,
                CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
                kCFRunLoopDefaultMode,
            )
            from Foundation import NSRunLoop, NSDate
            hotkey_mask = (1 << kCGEventKeyDown)

            def hotkey_callback(proxy, event_type, event, refcon):
                if event_type != kCGEventKeyDown:
                    return event
                flags = CGEventGetFlags(event)
                ctrl = bool(flags & kCGEventFlagMaskControl)
                shift = bool(flags & kCGEventFlagMaskShift)
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                if ctrl and shift and keycode == 15:
                    self.root.after(0, self._hotkey_toggle_record)
                    return event
                if ctrl and shift and keycode == 1:
                    self.root.after(0, self._hotkey_stop)
                    return event
                return event

            self._hotkey_tap = CGEventTapCreate(
                kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
                hotkey_mask, hotkey_callback, None,
            )
            if not self._hotkey_tap:
                from ApplicationServices import AXIsProcessTrusted
                logger.warning("全局热键注册失败: tap=None, AXIsProcessTrusted=%s", AXIsProcessTrusted())
                self.status_var.set("热键注册失败，录制功能仍可用")
                return
            CGEventTapEnable(self._hotkey_tap, True)
            source = CFMachPortCreateRunLoopSource(None, self._hotkey_tap, 0)
            rl = NSRunLoop.currentRunLoop().getCFRunLoop()
            CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)


            logger.info("全局热键已注册: Ctrl+Shift+R 识别, Ctrl+Shift+S 停止")
        except Exception as e:
            logger.warning("全局热键注册失败: %s", e)

    def _pump_ns_runloop(self):
        if not self.root.winfo_exists():
            return
        try:
            from Foundation import NSRunLoop, NSDate
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.02)
            )
        except Exception:
            pass
        self.root.after(50, self._pump_ns_runloop)

    def _hotkey_toggle_record(self):
        if self.recording:
            self._stop_record()
        elif not self.playing:
            self._start_record_silent()

    def _hotkey_stop(self):
        if self.recording:
            self._stop_record()
        elif self.playing:
            self._stop_play()

    def _start_record_silent(self):
        if self.recording:
            return
        import time as _time
        name = f"rec_{_time.strftime('%Y%m%d_%H%M%S')}"
        self.current_record_name = name
        ss_dir = os.path.join(self._scripts_dir, "scripts", f"{name}_screenshots")
        try:
            self.recorder = Recorder(screenshot_interval=2.0, screenshot_dir=ss_dir, ocr_anchors=True, visual_templates=True)
            self.recorder.start()
        except RuntimeError as e:
            self.status_var.set(f"权限错误: {e}")
            return
        self.recording = True
        self.record_start_time = time.time()
        self.btn_record.configure(text="■ 停止识别")
        self.btn_play.configure(state=tk.DISABLED)
        self.status_var.set("识别中... | ⌃⇧S 停止")
        self.root.iconify()
        self._update_record_count()

    def _check_update(self):
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _check_update_manual(self):
        self.status_var.set("正在检查更新...")
        threading.Thread(target=self._do_check_update, args=(True,), daemon=True).start()

    def _do_check_update(self, manual=False):
        info = mp.check_update()
        if info:
            self.root.after(0, self._show_update_dialog, info)
        elif manual:
            self.root.after(0, lambda: (
                self.status_var.set("已是最新版本"),
                messagebox.showinfo("检查更新", f"GhostAction v{mp.CURRENT_VERSION}\n已是最新版本")
            ))

    def _show_update_dialog(self, info):
        ver = info["version"]
        url = info.get("url", "")
        notes = info.get("notes", "")[:300]
        self.version_var.set(f"⬆️ v{ver} 可更新!")
        msg = f"发现新版本: v{ver}\n\n当前版本: v{mp.CURRENT_VERSION}\n\n"
        if notes:
            msg += f"更新内容:\n{notes}\n\n"
        msg += "是否前往下载？"
        if messagebox.askyesno("GhostAction 更新", msg):
            import webbrowser
            webbrowser.open(url) if url else None

    def _on_close(self):
        if self.recording:
            self._stop_record()
        if self.playing:
            self._stop_play()
        self.root.destroy()

    def _build_marketplace(self):
        for w in self.market_tab.winfo_children():
            w.destroy()

        search_frame = ttk.Frame(self.market_tab)
        search_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=(0, 4))
        self.market_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.market_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 4))
        search_entry.bind("<Return>", lambda e: self._market_search())
        ttk.Button(search_frame, text="🔍 搜索", command=self._market_search, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Button(search_frame, text="🔄 刷新", command=self._market_refresh, width=8).pack(side=tk.LEFT, padx=4)

        cols = ("name", "author", "tags", "steps", "description")
        self.market_tree = ttk.Treeview(self.market_tab, columns=cols, show="headings", height=10)
        self.market_tree.heading("name", text="脚本名")
        self.market_tree.heading("author", text="作者")
        self.market_tree.heading("tags", text="标签")
        self.market_tree.heading("steps", text="步骤")
        self.market_tree.heading("description", text="描述")
        self.market_tree.column("name", width=150)
        self.market_tree.column("author", width=80)
        self.market_tree.column("tags", width=120)
        self.market_tree.column("steps", width=50)
        self.market_tree.column("description", width=300)
        self.market_tree.pack(fill=tk.BOTH, expand=True)

        msb = ttk.Scrollbar(self.market_tab, orient=tk.VERTICAL, command=self.market_tree.yview)
        msb.pack(side=tk.RIGHT, fill=tk.Y)
        self.market_tree.configure(yscrollcommand=msb.set)

        action_frame = ttk.Frame(self.market_tab)
        action_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(action_frame, text="📥 下载", command=self._market_download, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="🔀 智能合并", command=self._market_merge, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="📋 详情", command=self._market_detail, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(action_frame, text="📤 共享到GitHub", command=self._share_script, width=14).pack(side=tk.LEFT, padx=3)

        self._market_refresh()


    def _market_refresh(self):
        self.status_var.set("正在加载脚本市场...")
        threading.Thread(target=self._do_market_refresh, daemon=True).start()

    def _do_market_refresh(self):
        scripts = mp.search_scripts()
        self.root.after(0, self._update_market_tree, scripts)

    def _market_search(self):
        keyword = self.market_search_var.get().strip()
        self.status_var.set(f"搜索: {keyword}...")
        threading.Thread(target=self._do_market_search, args=(keyword,), daemon=True).start()

    def _do_market_search(self, keyword):
        scripts = mp.search_scripts(keyword)
        self.root.after(0, self._update_market_tree, scripts)

    def _update_market_tree(self, remote_scripts):
        for item in self.market_tree.get_children():
            self.market_tree.delete(item)

        local_scripts = self.sm.list_all()
        for s in local_scripts:
            self.market_tree.insert("", tk.END, values=(
                s.get("name", ""),
                "本地",
                "📁 本地",
                s.get("events", ""),
                "",
            ), tags=("local",))

        for s in remote_scripts:
            self.market_tree.insert("", tk.END, values=(
                s.get("name", ""),
                s.get("author", ""),
                ", ".join(s.get("tags", [])),
                s.get("step_count", ""),
                s.get("description", ""),
            ), tags=("remote",))

        self.market_tree.tag_configure("local", foreground="#2563eb")
        self.market_tree.tag_configure("remote", foreground="#1a1a1a")
        self.status_var.set(f"市场: {len(local_scripts)} 本地 + {len(remote_scripts)} 远程")

    def _is_local_selected(self):
        sel = self.market_tree.selection()
        if not sel:
            return False
        tags = self.market_tree.item(sel[0]).get("tags", ())
        return "local" in tags

    def _get_selected_market_name(self):
        sel = self.market_tree.selection()
        if not sel:
            return None
        return self.market_tree.item(sel[0])["values"][0]

    def _get_selected_market_script(self):
        if self._is_local_selected():
            return None
        name = self._get_selected_market_name()
        if not name:
            return None
        index = mp.get_index()
        if not index:
            return None
        for s in index.get("scripts", []):
            if s.get("name") == name:
                return s
        return None

    def _market_download(self):
        if self._is_local_selected():
            messagebox.showinfo("提示", "这是本地脚本，无需下载")
            return
        entry = self._get_selected_market_script()
        if not entry:
            return
        self.status_var.set(f"下载中: {entry.get('name', '')}...")
        threading.Thread(target=self._do_market_download, args=(entry,), daemon=True).start()

    def _do_market_download(self, entry):
        data = mp.download_script(entry)
        if not data:
            self.root.after(0, lambda: messagebox.showerror("错误", "下载失败"))
            return
        name = entry.get("name", "downloaded")
        self.sm.save(name, data.get("events", []), data.get("meta"))
        self.root.after(0, self._after_market_download, name)

    def _after_market_download(self, name):
        self._refresh_scripts()
        self._market_refresh()
        self.status_var.set(f"已下载: {name}")
        messagebox.showinfo("成功", f"脚本 '{name}' 已下载到本地")

    def _market_merge(self):
        if self._is_local_selected():
            messagebox.showinfo("提示", "这是本地脚本，请选择远程脚本进行合并")
            return
        entry = self._get_selected_market_script()
        if not entry:
            return
        name = entry.get("name", "")
        local_data = self.sm.load(name)
        if not local_data:
            self._market_download()
            return
        self.status_var.set(f"合并中: {name}...")
        threading.Thread(target=self._do_market_merge, args=(entry, name, local_data), daemon=True).start()

    def _do_market_merge(self, entry, name, local_data):
        remote_data = mp.download_script(entry)
        if not remote_data:
            self.root.after(0, lambda: messagebox.showerror("错误", "下载远程脚本失败"))
            return
        merged, added, enhanced = mp.merge_scripts(local_data, remote_data)
        self.sm.save(name, merged.get("events", []), merged.get("meta"))
        self.root.after(0, self._after_market_merge, name, added, enhanced)

    def _after_market_merge(self, name, added, enhanced):
        self._refresh_scripts()
        self._market_refresh()
        self.status_var.set(f"已合并: {name} (+{added}步, 增强{enhanced}处)")
        messagebox.showinfo("合并完成", f"脚本 '{name}' 已合并\n新增 {added} 步\n增强 {enhanced} 处")

    def _market_detail(self):
        name = self._get_selected_market_name()
        if not name:
            return
        local_data = self.sm.load(name)
        local_fp = mp.compute_fingerprint(local_data) if local_data else None
        detail = f"脚本: {name}\n"
        if self._is_local_selected():
            detail += "来源: 📁 本地\n"
        else:
            entry = self._get_selected_market_script()
            if entry:
                detail += f"来源: 🌐 远程\n"
                detail += f"作者: {entry.get('author', '')}\n"
                detail += f"标签: {', '.join(entry.get('tags', []))}\n"
                detail += f"描述: {entry.get('description', '')}\n"
                detail += f"目标应用: {entry.get('target_app', '')}\n"
                detail += f"远程步骤数: {entry.get('step_count', '?')}\n"
        if local_fp:
            detail += f"\n--- 本地指纹 ---\n"
            detail += f"步骤数: {local_fp['step_count']}\n"
            detail += f"窗口数: {local_fp['window_count']}\n"
            detail += f"OCR覆盖率: {local_fp['ocr_coverage']:.0%}\n"
            detail += f"模板覆盖率: {local_fp['template_coverage']:.0%}\n"
            detail += f"逻辑链: {'有' if local_fp['has_logic_chain'] else '无'}\n"
        messagebox.showinfo("脚本详情", detail)

    def _share_script(self):
        if not self._is_local_selected():
            messagebox.showinfo("提示", "请选择一个本地脚本进行共享")
            return
        name = self._get_selected_market_name()
        if not name:
            return

        data = self.sm.load(name)
        if not data:
            return
        data["name"] = name
        script_json = json.dumps(data, ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(script_json)
        import subprocess
        import webbrowser
        gist_url = "https://gist.github.com/"
        try:
            webbrowser.open(gist_url)
        except Exception:
            subprocess.run(["open", gist_url])
        messagebox.showinfo("共享脚本",
            f"脚本 '{name}' 的JSON已复制到剪贴板！\n\n"
            f"操作步骤：\n"
            f"1. 浏览器已打开 GitHub Gist 页面\n"
            f"2. 在文件名处输入: {name}.json\n"
            f"3. 粘贴剪贴板内容 (⌘V)\n"
            f"4. 点击 'Create public gist'\n\n"
            f"创建后把Gist链接发到社区即可！")


def main():
    root = tk.Tk()
    app = AutoRepeatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
