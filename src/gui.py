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
    from win_recorder import WinRecorder as Recorder
    from win_player import WinPlayer as Player
    from win_recorder import get_visible_windows

from script_manager import ScriptManager

logger = logging.getLogger("gui")
action_log = logging.getLogger("action")
sync_log = logging.getLogger("sync")

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
        if tpl:
            parts.append("[截图]有截图")
        var = e.get("variable", "")
        if var:
            parts.append(f"[循环]变量:{var}")
        dom = e.get("dom_selector")
        if dom and dom.get("selectors"):
            parts.append(f"[浏览器]DOM:{dom['selectors'][0][:30]}")
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
        return "[截图] 自动截图"
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
        return f"[注释] {e.get('text', '')}"
    elif etype == "ai_recognize":
        target = e.get("target", "验证码")
        var = e.get("variable", "")
        return f"[AI] AI识别{target}" + (f" → {var}" if var else "")
    elif etype == "wait_manual":
        return f"|| 等待人工: {e.get('description', '请手动操作后继续')}"
    return etype


class AutoRepeatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GhostAction")
        self.root.geometry("1100x750")
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
        self._scheduler = None
        self._skill_hotkeys = {}
        self._event_watcher = None

        self._build_ui()
        self._refresh_scripts()
        self._init_scheduler()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(3000, self._check_update)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 8))

        self.btn_record = ttk.Button(ctrl, text="● 识别", command=self._toggle_record, width=12)
        self.btn_record.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_play = ttk.Button(ctrl, text="> 复现", command=self._play, width=12)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = ttk.Button(ctrl, text="|| 暂停", command=self._toggle_pause, width=8, state=tk.DISABLED)
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

        self.ai_status_var = tk.StringVar(value="")
        ttk.Label(row2, textvariable=self.ai_status_var, foreground="#999").pack(side=tk.RIGHT, padx=(0, 8))
        self.root.after(5000, self._update_ai_status)

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)

        scripts_tab = ttk.Frame(nb)
        nb.add(scripts_tab, text=" 脚本列表 ")

        search_row = ttk.Frame(scripts_tab)
        search_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(search_row, text="�指令:").pack(side=tk.LEFT, padx=(0, 4))
        self.script_search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.script_search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 4), fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self._nl_execute())
        ttk.Button(search_row, text="> 执行", command=self._nl_execute, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="[搜索]搜索", command=self._search_scripts, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="全部", command=self._refresh_scripts, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Separator(search_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(search_row, text="编辑", command=self._open_editor, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="[VIS]可视化", command=self._open_visual_editor, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="重命名", command=self._rename, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="删除", command=self._delete, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="刷新", command=self._refresh_scripts, width=4).pack(side=tk.LEFT, padx=2)

        cols = ("name", "events", "intent", "category", "created")
        self.tree = ttk.Treeview(scripts_tab, columns=cols, show="headings", height=8)
        self.tree.heading("name", text="脚本名")
        self.tree.heading("events", text="步骤")
        self.tree.heading("intent", text="意图")
        self.tree.heading("category", text="分类")
        self.tree.heading("created", text="创建时间")
        self.tree.column("name", width=150)
        self.tree.column("events", width=40)
        self.tree.column("intent", width=220)
        self.tree.column("category", width=60)
        self.tree.column("created", width=130)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(scripts_tab, orient=tk.VERTICAL, command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="编辑", command=self._open_editor)
        self.tree_menu.add_command(label="重命名", command=self._rename)
        self.tree_menu.add_command(label="删除", command=self._delete)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="刷新", command=self._refresh_scripts)
        if IS_MAC:
            self.tree.bind("<Button-2>", self._show_tree_menu)
            self.tree.bind("<Control-Button-1>", self._show_tree_menu)
        else:
            self.tree.bind("<Button-3>", self._show_tree_menu)


        self.editor_tab = ttk.Frame(nb)
        nb.add(self.editor_tab, text=" 编辑 ")

        self.market_tab = ttk.Frame(nb)
        nb.add(self.market_tab, text=" [市场] 市场 ")

        self.browser_tab = ttk.Frame(nb)
        nb.add(self.browser_tab, text=" [浏览器] 浏览器 ")

        self.scheduler_tab = ttk.Frame(nb)
        nb.add(self.scheduler_tab, text=" ⏰ 定时 ")

        self.watcher_tab = ttk.Frame(nb)
        nb.add(self.watcher_tab, text=" [监视] 触发 ")

        self._build_editor()
        self._build_marketplace()
        self._build_browser_tab()
        self._build_scheduler_tab()
        self._build_watcher_tab()
        self._start_hotkey_listener()
        self._pump_ns_runloop()

    def _build_editor(self):
        for w in self.editor_tab.winfo_children():
            w.destroy()

        top_frame = ttk.Frame(self.editor_tab)
        top_frame.pack(fill=tk.X, pady=(0, 4))
        self.editor_title_var = tk.StringVar(value="未加载脚本")
        ttk.Label(top_frame, textvariable=self.editor_title_var, font=("", 11, "bold")).pack(side=tk.LEFT)

        intent_frame = ttk.LabelFrame(self.editor_tab, text="逻辑链条 (可编辑)", padding=4)
        intent_frame.pack(fill=tk.X, pady=(0, 4))
        intent_btn_row = ttk.Frame(intent_frame)
        intent_btn_row.pack(fill=tk.X)
        ttk.Button(intent_btn_row, text="从步骤生成", command=self._regenerate_intent, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(intent_btn_row, text="AI优化", command=self._ai_optimize_intent, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(intent_btn_row, text="保存文本", command=self._save_intent_text, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(intent_btn_row, text="弹出编辑", command=self._popup_intent_editor, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(intent_btn_row, text="按窗口拆分", command=self._split_by_window, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(intent_btn_row, text="窗口黑名单", command=self._edit_window_blacklist, width=10).pack(side=tk.LEFT, padx=2)
        self.intent_text = tk.Text(intent_frame, height=3, wrap=tk.WORD, font=("", 10))
        self.intent_text.pack(fill=tk.X, pady=(2, 0))
        self.intent_var = tk.StringVar(value="")

        skill_frame = ttk.LabelFrame(self.editor_tab, text="⚡ Skill元数据")
        skill_frame.pack(fill=tk.X, pady=(0, 4))

        sf_row1 = ttk.Frame(skill_frame)
        sf_row1.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(sf_row1, text="触发词:").pack(side=tk.LEFT, padx=(0, 4))
        self.triggers_var = tk.StringVar(value="")
        ttk.Entry(sf_row1, textvariable=self.triggers_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(sf_row1, text="(逗号分隔)", foreground="#999").pack(side=tk.LEFT, padx=4)

        sf_row2 = ttk.Frame(skill_frame)
        sf_row2.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(sf_row2, text="分类:").pack(side=tk.LEFT, padx=(0, 4))
        self.category_var = tk.StringVar(value="")
        ttk.Combobox(sf_row2, textvariable=self.category_var, values=["通讯", "浏览器", "办公", "文件管理", "开发", "设计", "其他"], width=10, state="readonly").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(sf_row2, text="标签:").pack(side=tk.LEFT, padx=(0, 4))
        self.tags_var = tk.StringVar(value="")
        ttk.Entry(sf_row2, textvariable=self.tags_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(sf_row2, text="(逗号分隔)", foreground="#999").pack(side=tk.LEFT, padx=4)

        sf_row3 = ttk.Frame(skill_frame)
        sf_row3.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(sf_row3, text="参数:").pack(side=tk.LEFT, padx=(0, 4))
        self.params_var = tk.StringVar(value="")
        ttk.Entry(sf_row3, textvariable=self.params_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(sf_row3, text="(格式: 名称:描述, ...)", foreground="#999").pack(side=tk.LEFT, padx=4)

        sf_row4 = ttk.Frame(skill_frame)
        sf_row4.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(sf_row4, text="引擎:").pack(side=tk.LEFT, padx=(0, 4))
        self.engine_var = tk.StringVar(value="auto")
        ttk.Combobox(sf_row4, textvariable=self.engine_var, values=["auto", "browser_dom", "browser", "mouse"], width=12, state="readonly").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(sf_row4, text="浏览器身份:").pack(side=tk.LEFT, padx=(0, 4))
        self.browser_profile_var = tk.StringVar(value="")
        ttk.Entry(sf_row4, textvariable=self.browser_profile_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(sf_row4, text="(留空=自动)", foreground="#999").pack(side=tk.LEFT, padx=4)

        sf_row5 = ttk.Frame(skill_frame)
        sf_row5.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(sf_row5, text="快捷键:").pack(side=tk.LEFT, padx=(0, 4))
        self.hotkey_var = tk.StringVar(value="")
        ttk.Entry(sf_row5, textvariable=self.hotkey_var, width=20).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(sf_row5, text="(如: Ctrl+Shift+1, 留空=无)", foreground="#999").pack(side=tk.LEFT, padx=4)

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
        ttk.Button(btn_row1, text="[保存]保存", command=self._editor_save, width=6).pack(side=tk.RIGHT, padx=2)

        btn_row2 = ttk.Frame(self.editor_tab)
        btn_row2.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_row2, text="➕点选添加", command=self._editor_pick_element, width=9).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="[循环]变量", command=self._editor_bind_variable, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="[数据]数据源", command=self._editor_set_data_source, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="[AI]AI识别", command=self._editor_insert_ai_recognize, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row2, text="AI设置", command=self._show_ai_settings, width=8).pack(side=tk.LEFT, padx=2)
        self.ai_fallback_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_row2, text="AI兜底", variable=self.ai_fallback_var).pack(side=tk.LEFT, padx=4)
        self.smart_replay_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_row2, text="智能回放", variable=self.smart_replay_var).pack(side=tk.LEFT, padx=4)
        self.visual_match_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btn_row2, text="视觉匹配", variable=self.visual_match_var).pack(side=tk.LEFT, padx=4)

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

        self.chain_frame = ttk.LabelFrame(bottom_frame, text="[列表] 操作逻辑链")
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
        action_log.info("开始录制 speed=%.1f", self.speed_var.get())
        name = _ask_string(self.root, "识别", "输入脚本名称:")
        if not name:
            return
        name = name.strip().replace(" ", "_")
        self.current_record_name = name
        ss_dir = os.path.join(self._scripts_dir, "scripts", f"{name}_screenshots")
        try:
            self.recorder = Recorder(screenshot_interval=2.0, screenshot_dir=ss_dir, ocr_anchors=True, visual_templates=True,
                                     browser_engine=getattr(self, '_browser_engine', None))
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
        action_log.info("停止录制 events=%d", len(self._current_events))
        if not self.recorder:
            return
        self.status_var.set("处理中...")
        self.root.update_idletasks()
        events = self.recorder.stop()
        self.recording = False

        pids = [e.get("pid") for e in events if e.get("pid")]
        pid_counter = Counter(pids)
        pid_names = {}
        for e in events:
            pid = e.get("pid")
            if not pid or pid in pid_names:
                continue
            win = e.get("window") or {}
            owner = win.get("owner", "")
            if owner:
                pid_names[pid] = owner
        if get_visible_windows:
            for w in get_visible_windows():
                if w["pid"] not in pid_names and w.get("owner"):
                    pid_names[w["pid"]] = w["owner"]
        for pid, count in pid_counter.most_common():
            if pid not in pid_names:
                pid_names[pid] = f"PID:{pid}"

        click_count = sum(1 for e in events if e["type"] == "mouse_down")
        key_count = sum(1 for e in events if e["type"] == "key_down")
        drag_count = sum(1 for e in events if e["type"] == "mouse_drag")
        meta = {
            "clicks": click_count, "keys": key_count, "drags": drag_count,
            "duration": round(time.time() - self.record_start_time, 1),
            "pid_names": pid_names,
        }

        logic_chain = self._build_logic_chain(events, pid_names, skip_ocr=True)
        meta["logic_chain"] = logic_chain

        intent = self._logic_chain_to_intent(logic_chain)
        try:
            import ai_recognizer
            self.status_var.set("AI优化意图描述中...")
            self.root.update_idletasks()
            ai_intent = ai_recognizer.generate_intent_with_fallback(events, meta)
            if ai_intent:
                intent = ai_intent
        except Exception as e:
            logger.warning("AI意图生成失败: %s", e)

        self.sm.save(self.current_record_name, events, meta, intent=intent, skill_meta=self.sm.auto_generate_skill_meta(events, meta, intent))
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
        if not hasattr(self, '_screenshot_cache') or self._screenshot_cache_events is not events:
            self._screenshot_cache = [(i, e) for i, e in enumerate(events) if e.get("type") == "screenshot" and e.get("file")]
            self._screenshot_cache_events = events
        click_e = events[click_idx]
        cx, cy = click_e.get("x", 0), click_e.get("y", 0)
        click_time = click_e.get("time", 0)
        best_ss = None
        best_dt = float("inf")
        for i, e in self._screenshot_cache:
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

    def _build_logic_chain(self, events, pid_names, skip_ocr=False):
        sync_log.debug("构建逻辑链条")
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
                tpl = e.get("template", "")
                tpl_path = ""
                if tpl and self._scripts_dir:
                    for subdir in ["scripts/templates", "templates"]:
                        tp = os.path.join(self._scripts_dir, subdir, tpl)
                        if os.path.exists(tp):
                            tpl_path = tp
                            break
                if tpl_path and not skip_ocr:
                    try:
                        from ocr_corrections import lookup_correction
                        corrected = lookup_correction(tpl_path)
                        if corrected:
                            ocr_text = corrected
                    except Exception:
                        pass
                ax = e.get("ax_element", {})
                ax_title = ax.get("AXTitle", "") if ax else ""
                ax_role = ax.get("AXRole", "") if ax else ""
                ax_desc = ax.get("AXDescription", "") if ax else ""
                tpl = e.get("template", "")

                desc_parts = []
                ocr_valid = ocr_text and len(ocr_text) >= 2 and not all(c in ".-0123456789()©' " for c in ocr_text)
                if ocr_valid:
                    desc_parts.append(f"「{ocr_text}」")
                if ax_title and len(ax_title) >= 1:
                    desc_parts.append(f"「{ax_title}」")
                elif ax_desc and len(ax_desc) >= 1:
                    desc_parts.append(f"「{ax_desc}」")

                role_cn = {"AXButton": "按钮", "AXStaticText": "文本", "AXTextField": "输入框",
                           "AXCheckBox": "复选框", "AXRadioButton": "单选按钮", "AXMenu": "菜单",
                           "AXMenuItem": "菜单项", "AXLink": "链接", "AXTabGroup": "标签页",
                           "AXPopUpButton": "下拉框", "AXTable": "表格", "AXRow": "行",
                           }.get(ax_role, "")

                if not desc_parts:
                    if role_cn:
                        desc_parts.append(role_cn)
                    if not skip_ocr:
                        ss_ocr = self._ocr_click_region(events, idx)
                        if ss_ocr and len(ss_ocr) >= 2 and not all(c in ".-0123456789()©' " for c in ss_ocr):
                            desc_parts.append(f"「{ss_ocr}」")
                        elif not desc_parts:
                            enhanced = self._enhanced_ocr_at(e.get("x", 0), e.get("y", 0), pid)
                            if enhanced:
                                desc_parts.append(f"「{enhanced}」")

                if not desc_parts and role_cn:
                    desc_parts = [role_cn]

                desc = "".join(desc_parts) if desc_parts else f"区域({e.get('x', 0):.0f},{e.get('y', 0):.0f})"
                step = {
                    "type": "click",
                    "button": btn_cn,
                    "desc": desc,
                    "x": e.get("x", 0), "y": e.get("y", 0),
                    "pid": pid, "window": last_window,
                    "ocr": ocr_text, "ax_title": ax_title, "ax_role": ax_role,
                    "template": tpl,
                    "event_idx": idx,
                }
                if tpl and self._scripts_dir:
                    for subdir in ["scripts/templates", "templates"]:
                        sp = os.path.join(self._scripts_dir, subdir, tpl)
                        if os.path.exists(sp):
                            step["screenshot_path"] = sp
                            break
                if e.get("modifiers"):
                    step["modifiers"] = e["modifiers"]
                steps.append(step)

            elif e["type"] == "key_down":
                text = e.get("text", "")
                keycode = e.get("keycode", 0)
                mods = e.get("modifiers", [])
                if text and text.isprintable() and len(text) == 1:
                    step = {"type": "input", "text": text, "pid": pid, "window": last_window, "event_idx": idx}
                else:
                    key_name = {"cmd": "⌘", "shift": "⇧", "ctrl": "⌃", "alt": "⌥"}
                    mod_str = "".join(key_name.get(m, m) for m in mods)
                    kc_names = {36: "↵", 48: "⌫", 51: "⌦", 49: "空格", 53: "⎋"}
                    kn = kc_names.get(keycode, f"键{keycode}")
                    step = {"type": "keypress", "key": f"{mod_str}{kn}", "pid": pid, "window": last_window, "event_idx": idx}
                steps.append(step)

            elif e["type"] == "scroll":
                dy = e.get("dy", 0)
                direction = "上滚" if dy > 0 else "下滚"
                steps.append({"type": "scroll", "direction": direction, "amount": abs(dy), "pid": pid, "window": last_window, "event_idx": idx})

        return steps

    def _logic_chain_to_intent(self, chain):
        sync_log.debug("链条转文本")
        if not chain:
            return ""
        # Merge consecutive same actions
        merged = []
        for step in chain:
            stype = step.get("type", "")
            if stype == "switch_window":
                merged.append(step)
                continue
            key = f"{stype}:{step.get('desc', '') or step.get('text', '') or step.get('key', '') or step.get('direction', '')}"
            if merged and not merged[-1].get("type") == "switch_window":
                prev_key = f"{merged[-1].get('type')}:{merged[-1].get('desc', '') or merged[-1].get('text', '') or merged[-1].get('key', '') or merged[-1].get('direction', '')}"
                if key == prev_key:
                    merged[-1]["_count"] = merged[-1].get("_count", 1) + 1
                    continue
            step = dict(step)
            step["_count"] = 1
            merged.append(step)

        # Split by window into sections
        sections = []
        current_window = ""
        current_steps = []
        for step in merged:
            if step.get("type") == "switch_window":
                if current_steps:
                    sections.append((current_window, current_steps))
                current_window = step.get("target", "")
                current_steps = []
            else:
                current_steps.append(step)
        if current_steps:
            sections.append((current_window, current_steps))

        # Format as tree text
        lines = []
        for window, steps in sections:
            if window:
                lines.append(f"[{window}]")
            for step in steps:
                count = step.get("_count", 1)
                stype = step.get("type", "")
                if stype == "click":
                    desc = step.get("desc", "")
                    btn = step.get("button", "左键")
                    action = f"右键{desc}" if btn == "右键" else f"点击{desc}"
                    lines.append(f"  {action}" + (f" x{count}" if count > 1 else ""))
                elif stype == "input":
                    text = step.get("text", "")
                    lines.append(f"  输入[{text}]" + (f" x{count}" if count > 1 else ""))
                elif stype == "keypress":
                    key = step.get("key", "")
                    lines.append(f"  按{key}" + (f" x{count}" if count > 1 else ""))
                elif stype == "scroll":
                    direction = step.get("direction", "")
                    lines.append(f"  {direction}滚动" + (f" x{count}" if count > 1 else ""))
        return "\n".join(lines)


    def _enhanced_ocr_at(self, x, y, pid=None):
        sync_log.debug("增强OCR识别")
        if not x or not y:
            return ""
        try:
            import pytesseract
            from PIL import Image
            from Quartz import CGWindowListCreateImage, kCGNullWindowID, kCGWindowListOptionOnScreenOnly
            import numpy as np
            from Quartz import CGRectInfinite
            cg_img = CGWindowListCreateImage(CGRectInfinite, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, 0)
            if not cg_img:
                return ""
            from Quartz import CGImageGetWidth, CGImageGetHeight, CGImageGetBytesPerRow, CGImageGetDataProvider
            from Quartz import CGDataProviderCopyData
            w = CGImageGetWidth(cg_img)
            h = CGImageGetHeight(cg_img)
            bpr = CGImageGetBytesPerRow(cg_img)
            data = CGDataProviderCopyData(CGImageGetDataProvider(cg_img))
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, bpr // 4, 4)
            full_img = Image.fromarray(arr[:, :w, :3], "RGB")
            region_size = 150
            left = max(0, int(x) - region_size)
            top = max(0, int(y) - region_size)
            right = min(w, int(x) + region_size)
            bottom = min(h, int(y) + region_size)
            crop = full_img.crop((left, top, right, bottom))
            results = pytesseract.image_to_data(crop, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
            best = ""
            best_dist = 999999
            cx, cy = int(x) - left, int(y) - top
            for i, t in enumerate(results["text"]):
                if not t or len(t) < 2:
                    continue
                if all(c in ".-0123456789()©' " for c in t):
                    continue
                bx = results["left"][i] + results["width"][i] // 2
                by = results["top"][i] + results["height"][i] // 2
                dist = (bx - cx) ** 2 + (by - cy) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best = t
            return best if best_dist < 10000 else ""
        except Exception:
            return ""

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
        action_log.info("开始回放 script=%s speed=%.1f smart=%s visual=%s", name, self.speed_var.get(), self.smart_replay_var.get(), self.visual_match_var.get())
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

        skill_meta = data.get("skill_meta", {})
        skill_params = skill_meta.get("params", [])
        user_vars = {}
        if skill_params:
            user_vars = self._ask_skill_params(name, skill_params)
            if user_vars is None:
                return

        if has_variables and not data_source and not user_vars:
            messagebox.showwarning("提示", "脚本包含变量标记，但未绑定数据源。\n请在编辑器中点击「[数据]数据源」按钮绑定数据文件。")
            return

        engine_type = skill_meta.get("engine", "auto")
        browser_profile = skill_meta.get("browser_profile")
        browser_engine = getattr(self, '_browser_engine', None)

        if engine_type in ("browser", "browser_dom") and browser_engine and browser_engine.is_connected():
            if browser_profile and browser_profile not in [s["id"] for s in getattr(self, '_browser_sessions', [])]:
                sid, page = browser_engine.new_identity(headless=False)
                if sid:
                    self._browser_sessions.append({"id": sid, "page": page})
                    browser_profile = sid
            elif not browser_profile:
                browser_profile = browser_engine.get_active_session_id()

        self.player = Player(speed=speed, target_pid=target_pid, smart_replay=self.smart_replay_var.get(),
                             visual_match=self.visual_match_var.get(), scripts_dir=self._scripts_dir,
                             retry_count=3, on_error="continue",
                             use_ai_fallback=self.ai_fallback_var.get(),
                             browser_engine=browser_engine if engine_type in ("browser", "browser_dom", "auto") else None,
                             browser_profile=browser_profile)
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
            self.player.play(events, variables=user_vars, data_source=ds_info)
            self.root.after(0, self._on_play_done, name)

        threading.Thread(target=run, daemon=True).start()

    def _toggle_pause(self):
        action_log.info("暂停/继续回放")
        if not self.player:
            return
        if self.btn_pause.cget("text") == "|| 暂停":
            self.player.pause()
            self.btn_pause.configure(text="> 继续")
            self.status_var.set("复现已暂停")
        else:
            self.player.resume()
            self.btn_pause.configure(text="|| 暂停")
            self.status_var.set("复现中...")

    def _on_play_done(self, name):
        self.playing = False
        self.btn_play.configure(state=tk.NORMAL)
        self.btn_record.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED, text="|| 暂停")
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
        action_log.info("停止回放")
        if self.player:
            self.player.stop()
        self.playing = False
        self.btn_play.configure(state=tk.NORMAL)
        self.btn_record.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED, text="|| 暂停")
        self.btn_stop_play.configure(state=tk.DISABLED)
        self.status_var.set("复现已停止")
        self.root.deiconify()

    def _refresh_scripts(self):
        sync_log.debug("刷新脚本列表")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.sm.list_all():
            intent_short = (s.get("intent", "")[:30] + "...") if len(s.get("intent", "")) > 30 else s.get("intent", "")
            self.tree.insert("", tk.END, values=(s["name"], s["events"], intent_short, s.get("category", ""), s["created"]))

    def _search_scripts(self):
        query = self.script_search_var.get().strip()
        if not query:
            self._refresh_scripts()
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.sm.search(query):
            intent_short = (s.get("intent", "")[:30] + "...") if len(s.get("intent", "")) > 30 else s.get("intent", "")
            self.tree.insert("", tk.END, values=(s["name"], s["events"], intent_short, s.get("category", ""), s["created"]))

    def _rename(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        old_name = item["values"][0]
        new_name = _ask_string(self.root, "重命名", "新名称:", initialvalue=old_name)
        action_log.info("重命名脚本 old=%s new=%s", old_name, new_name)
        if new_name and new_name != old_name:
            data = self.sm.load(old_name)
            if data:
                data["name"] = new_name
                self.sm.save(new_name, data["events"], data.get("meta"))
                self.sm.delete(old_name)
                self._refresh_scripts()

    def _show_tree_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        action_log.info("删除脚本 name=%s", name)
        if messagebox.askyesno("确认", f"删除脚本: {name}?"):
            self.sm.delete(name)
            self._refresh_scripts()


    def _open_visual_editor(self):
        sel = self.tree.selection()
        name = None
        events = []
        if sel:
            item = self.tree.item(sel[0])
            name = item["values"][0]
            action_log.info("打开可视化编辑器 name=%s", name)
            try:
                data = self.sm.load(name)
                events = data.get("events", []) if data else []
            except Exception as e:
                action_log.warning("加载脚本失败: %s", e)
        else:
            action_log.info("打开可视化编辑器(空)")
        try:
            from visual_editor import VisualEditor
            if not hasattr(self, '_visual_editor'):
                self._visual_editor = VisualEditor(
                    scripts_dir=self._scripts_dir,
                    on_save=lambda ev, xml: self._visual_editor_save_with_name(name or "untitled", ev, xml),
                    on_run=self._visual_editor_run,
                )
            self._visual_editor._on_save_cb = lambda ev, xml: self._visual_editor_save_with_name(name or "untitled", ev, xml)
            self._visual_editor.open(events=events)
        except ImportError:
            messagebox.showerror("错误", "pywebview未安装\n请运行: pip install pywebview")
        except Exception as e:
            messagebox.showerror("错误", f"可视化编辑器启动失败: {e}")

    def _visual_editor_save_with_name(self, script_name, events, blockly_xml=""):
        try:
            self.sm.save(script_name, events, {"blockly_xml": blockly_xml, "source": "visual_editor"})
            self._refresh_scripts()
            action_log.info("可视化编辑器保存: %s (%d events)", script_name, len(events))
            return {"ok": True, "name": script_name}
        except Exception as e:
            action_log.error("可视化编辑器保存失败: %s", e)
            return {"ok": False, "error": str(e)}

    def _visual_editor_run(self, events):
        try:
            action_log.info("可视化编辑器运行: %d events", len(events))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _open_editor(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个脚本")
            return
        item = self.tree.item(sel[0])
        name = item["values"][0]
        action_log.info("打开编辑器 name=%s", name)
        self._open_editor_for_script(name)

    def _new_script(self):
        name = _ask_string(self.root, "新建脚本", "脚本名称:")
        if not name:
            return
        action_log.info("新建脚本 name=%s", name)
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
        import time as _time
        t0 = _time.time()
        data = self.sm.load(name)
        if not data:
            messagebox.showerror("错误", f"脚本不存在: {name}")
            return
        t1 = _time.time()
        logger.info("[PERF] sm.load: %.0fms", (t1 - t0) * 1000)
        self._current_script_name = name
        self._current_events = data.get("events", [])
        self.editor_title_var.set(f"编辑: {name} ({len(self._current_events)} 步)")
        self.intent_text.delete("1.0", tk.END)
        self.intent_text.insert("1.0", data.get("intent", ""))
        sm = data.get("skill_meta", {})
        self.triggers_var.set(",".join(sm.get("triggers", [])))
        self.category_var.set(sm.get("category", ""))
        self.tags_var.set(",".join(sm.get("tags", [])))
        params_list = sm.get("params", [])
        params_str = ",".join(f"{p.get('name','')}:{p.get('desc','')}" for p in params_list)
        self.params_var.set(params_str)
        self.engine_var.set(sm.get("engine", "auto"))
        self.browser_profile_var.set(sm.get("browser_profile", "") or "")
        self.hotkey_var.set(sm.get("hotkey", "") or "")
        t2 = _time.time()
        logger.info("[PERF] UI字段填充: %.0fms", (t2 - t1) * 1000)

        pid_names = data.get("meta", {}).get("pid_names", {})
        if not pid_names:
            for e in self._current_events:
                pid = e.get("pid")
                if pid and pid not in pid_names:
                    win = e.get("window") or {}
                    owner = win.get("owner", "")
                    if owner:
                        pid_names[pid] = owner

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
        t3 = _time.time()
        logger.info("[PERF] pid_names构建: %.0fms", (t3 - t2) * 1000)

        self._populate_editor()
        t4 = _time.time()
        logger.info("[PERF] _populate_editor: %.0fms", (t4 - t3) * 1000)

        self._show_logic_chain(data)
        t5 = _time.time()
        logger.info("[PERF] _show_logic_chain: %.0fms", (t5 - t4) * 1000)

        nb = self.root.winfo_children()
        for child in nb:
            if isinstance(child, ttk.Notebook):
                child.select(1)
                break
        t6 = _time.time()
        logger.info("[PERF] 编辑器总耗时: %.0fms (events=%d)", (t6 - t0) * 1000, len(self._current_events))

    def _apply_window_filter(self, event=None):
        sync_log.debug("应用窗口过滤")
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
        sync_log.debug("合并点击")
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
        sync_log.debug("移除截图")
        self._current_events = [e for e in self._current_events if e.get("type") != "screenshot"]
        self._populate_editor()

    def _show_logic_chain(self, data):
        import time as _time
        t0 = _time.time()
        events = data.get("events", [])
        pid_names = data.get("meta", {}).get("pid_names", {})
        chain = self._build_logic_chain(events, pid_names, skip_ocr=True)
        t1 = _time.time()
        logger.info("[PERF] _build_logic_chain: %.0fms (chain=%d)", (t1 - t0) * 1000, len(chain))
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
                self.chain_text.insert(tk.END, f"[窗口] {win}\n", "window_header")
                current_window = win

            if s["type"] == "switch_window":
                self.chain_text.insert(tk.END, f"  [滚动] 切换到: {s['target']}\n", "switch")
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
        if self._current_script_name:
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
            detail = e.get("intent") or _human_event_detail(e, self._scripts_dir)

            icon_map = {
                "mouse_down": "[点击]", "mouse_drag": "[拖动]", "scroll": "[滚动]",
                "key_down": "[按键]", "type_text": "[按键]", "screenshot": "[截图]",
                "wait_for": "[等待]", "assert_that": "[OK]", "activate": "[窗口]",
                "if": "[分支]", "endif": "[结束]", "for": "[循环]", "endfor": "[结束]",
                "while": "[循环]", "endwhile": "[结束]", "set_variable": "[变量]",
                "call_script": "[调用]", "comment": "[注释]", "ai_recognize": "[AI]", "wait_manual": "||",
            }
            icon = icon_map.get(etype, "•")

            pid = e.get("pid")
            window_str = ""
            if pid:
                window_str = pid_names.get(pid, f"PID:{pid}")

            disabled = "[X]" if e.get("disabled") else ""

            if window_str not in window_groups:
                window_groups[window_str] = []
            window_groups[window_str].append((step_num, icon, detail, window_str, disabled, i))

        for win_name, items in window_groups.items():
            group_label = f"[窗口] {win_name}" if win_name else "[窗口] 未知窗口"
            group_id = self.editor_tree.insert("", tk.END, values=("", "", group_label, "", ""), open=True)
            for step_num, icon, detail, window_str, disabled, idx in items:
                self.editor_tree.insert(group_id, tk.END, iid=f"evt_{idx}", values=(step_num, icon, detail, window_str, disabled))

    def _on_editor_select(self, event=None):
        sync_log.debug("编辑器选择步骤")
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
                    parts.append(f"[截图] 模板截图: {tpl}")
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
        sync_log.debug("编辑器双击步骤")
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
        action_log.info("切换步骤启用/禁用")
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
        action_log.info("删除步骤")
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
        action_log.info("插入等待")
        idx = self._get_selected_event_idx()
        timeout = _ask_integer(self.root, "等待", "等待秒数:", initialvalue=3) or 3
        ev = {"type": "wait_for", "strategy": "template", "timeout": timeout, "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_assert(self):
        action_log.info("插入断言")
        idx = self._get_selected_event_idx()
        desc = _ask_string(self.root, "断言", "断言描述:") or ""
        ev = {"type": "assert_that", "strategy": "template", "description": desc, "timeout": 5, "on_fail": "warn", "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_for(self):
        action_log.info("插入循环")
        idx = self._get_selected_event_idx()
        n = _ask_integer(self.root, "循环", "循环次数:", initialvalue=3) or 3
        ev_for = {"type": "for", "count": n, "variable": "_i", "time": 0}
        ev_endfor = {"type": "endfor", "time": 0}
        self._current_events.insert(idx, ev_for)
        self._current_events.insert(idx + 1, ev_endfor)
        self._populate_editor()

    def _editor_insert_comment(self):
        action_log.info("插入注释")
        idx = self._get_selected_event_idx()
        text = _ask_string(self.root, "注释", "注释内容:") or ""
        ev = {"type": "comment", "text": text, "time": 0}
        self._current_events.insert(idx, ev)
        self._populate_editor()

    def _editor_insert_ai_recognize(self):
        action_log.info("插入AI识别")
        if not self._current_script_name:
            self._new_script()
            if not self._current_script_name:
                return

        top = tk.Toplevel(self.root)
        top.title("[AI] 添加AI识别步骤")
        top.geometry("450x350")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="AI识别步骤：根据模式调用视觉AI或文本AI", font=("", 10, "bold"), wraplength=420).pack(anchor="w", pady=(0, 8))

        row0 = ttk.Frame(frm)
        row0.pack(fill=tk.X, pady=4)
        ttk.Label(row0, text="识别模式:").pack(side=tk.LEFT, padx=(0, 4))
        mode_var = tk.StringVar(value="vision")
        mode_combo = ttk.Combobox(row0, textvariable=mode_var, values=["vision:图像识别(验证码/图形)", "text:文本问答(答题/推理)"], width=30, state="readonly")
        mode_combo.pack(side=tk.LEFT)
        mode_combo.current(0)

        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="识别目标:").pack(side=tk.LEFT, padx=(0, 4))
        target_var = tk.StringVar(value="验证码")
        ttk.Combobox(row1, textvariable=target_var, values=["验证码", "文字", "数字", "图形", "答题"], width=12, state="readonly").pack(side=tk.LEFT)

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
            mode_str = mode_var.get()
            mode = "text" if mode_str.startswith("text") else "vision"
            ev = {
                "type": "ai_recognize",
                "target": target,
                "variable": var,
                "mode": mode,
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
        top.title(" AI模型设置")
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

            signup_url = pinfo.get("signup_url", "")
            if signup_url:
                def _open_signup(url=signup_url):
                    import webbrowser
                    webbrowser.open(url)
                ttk.Button(kf, text="申请Key", command=_open_signup, width=7).pack(side=tk.LEFT, padx=4)

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
        ttk.Label(vmf, text="[AI] 图形识别模型:").pack(side=tk.LEFT, padx=(0, 4))
        vision_models = [k for k, v in ai.MODEL_REGISTRY.items() if "vision" in v["capabilities"]]
        vision_var = tk.StringVar(value=config.get("vision_model", "glm-4v-flash"))
        ttk.Combobox(vmf, textvariable=vision_var, values=vision_models, width=22, state="readonly").pack(side=tk.LEFT)

        tmf = ttk.Frame(model_frame)
        tmf.pack(fill=tk.X, pady=2)
        ttk.Label(tmf, text="[变量] 文本推理模型:").pack(side=tk.LEFT, padx=(0, 4))
        text_models = [k for k, v in ai.MODEL_REGISTRY.items() if "text" in v["capabilities"]]
        text_var = tk.StringVar(value=config.get("text_model", "deepseek-chat"))
        ttk.Combobox(tmf, textvariable=text_var, values=text_models, width=22, state="readonly").pack(side=tk.LEFT)

        status_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=status_var, foreground="#2563eb").pack(anchor="w", pady=4)

        def _test():
            model_key = vision_var.get()
            model_info = ai.MODEL_REGISTRY.get(model_key)
            if not model_info:
                status_var.set("[X] 未知模型")
                return
            provider = model_info["provider"]
            api_key = key_entries.get(provider, tk.StringVar()).get()
            ok, msg = ai.test_connection(model_key, api_key)
            status_var.set(f"{'[OK]' if ok else '[X]'} {msg}")

        def _save():
            for provider_key in all_providers:
                if provider_key not in config["providers"]:
                    config["providers"][provider_key] = {}
                config["providers"][provider_key]["api_key"] = key_entries[provider_key].get()
                config["providers"][provider_key]["enabled"] = key_entries[f"{provider_key}_enabled"].get()
            config["vision_model"] = vision_var.get()
            config["text_model"] = text_var.get()
            ai.save_config(config)
            status_var.set("[OK] 设置已保存")
            self.status_var.set("AI设置已保存")

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="测试连接", command=_test, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="保存", command=_save, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="关闭", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _editor_pick_element(self):
        action_log.info("选取元素")
        if not self._current_script_name:
            self._new_script()
            if not self._current_script_name:
                return
        self.status_var.set("[*] 点选模式：点击屏幕上的目标元素，按 Esc 取消...")
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
        top.title("[*] 添加步骤")
        top.geometry("500x450")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        info_parts = [f"[坐标] 坐标: ({x:.0f}, {y:.0f})"]
        if window_owner:
            info_parts.append(f"[窗口] 窗口: {window_owner}")
        if ax_element:
            role = ax_element.get("AXRoleDescription", ax_element.get("AXRole", ""))
            title = ax_element.get("AXTitle", "")
            desc = ax_element.get("AXDescription", "")
            val = ax_element.get("AXValue", "")
            if role:
                info_parts.append(f"[工具] 元素: {role}")
            if title:
                info_parts.append(f"[标记] 标题: {title}")
            elif desc:
                info_parts.append(f"[标记] 描述: {desc}")
            if val:
                info_parts.append(f"[变量] 值: {val[:50]}")
        if ocr_anchor:
            info_parts.append(f"[搜索] OCR: 「{ocr_anchor['text']}」")

        ttk.Label(frm, text="\n".join(info_parts), font=("", 10), wraplength=460, justify=tk.LEFT).pack(anchor="w", pady=(0, 8))

        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        ttk.Label(frm, text="选择动作:", font=("", 10, "bold")).pack(anchor="w", pady=(4, 4))

        action_var = tk.StringVar(value="click")
        actions_frame = ttk.Frame(frm)
        actions_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Radiobutton(actions_frame, text="[点击] 点击", variable=action_var, value="click").pack(anchor="w", pady=2)
        ttk.Radiobutton(actions_frame, text="[按键] 输入文字", variable=action_var, value="type").pack(anchor="w", pady=2)
        ttk.Radiobutton(actions_frame, text="[按键] 输入变量 {{变量名}}", variable=action_var, value="type_var").pack(anchor="w", pady=2)
        if ax_actions and "AXPress" in ax_actions:
            ttk.Radiobutton(actions_frame, text="[选项] Accessibility点击 (AXPress)", variable=action_var, value="ax_press").pack(anchor="w", pady=2)

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
        action_log.info("绑定变量")
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

        ttk.Label(frm, text=f"[数据] 数据源: {os.path.basename(path)}", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
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
            data["intent"] = self.intent_text.get("1.0", tk.END).strip()
            triggers = [t.strip() for t in self.triggers_var.get().split(",") if t.strip()]
            tags = [t.strip() for t in self.tags_var.get().split(",") if t.strip()]
            params_raw = self.params_var.get().strip()
            params = []
            if params_raw:
                for p in params_raw.split(","):
                    p = p.strip()
                    if ":" in p:
                        pname, pdesc = p.split(":", 1)
                        params.append({"name": pname.strip(), "type": "string", "required": False, "desc": pdesc.strip()})
                    elif p:
                        params.append({"name": p, "type": "string", "required": False, "desc": ""})
            skill_meta = {
                "triggers": triggers,
                "params": params,
                "assertions": data.get("skill_meta", {}).get("assertions", []),
                "category": self.category_var.get(),
                "tags": tags,
                "engine": self.engine_var.get(),
                "browser_profile": self.browser_profile_var.get().strip() or None,
                "hotkey": self.hotkey_var.get().strip() or None,
            }
            self.sm.save(self._current_script_name, self._current_events, data.get("meta"), intent=data.get("intent", ""), skill_meta=skill_meta)
            self.status_var.set(f"已保存: {self._current_script_name}")
            self._refresh_scripts()

    def _regenerate_intent(self):
        if not self._current_events:
            return
        pid_names = {}
        data = self.sm.load(self._current_script_name) if self._current_script_name else None
        if data:
            pid_names = data.get("meta", {}).get("pid_names", {})
        chain = self._build_logic_chain(self._current_events, pid_names, skip_ocr=True)
        intent = self._logic_chain_to_intent(chain)
        self.intent_text.delete("1.0", tk.END)
        self.intent_text.insert("1.0", intent)
        self.status_var.set("逻辑链条已从步骤生成")



    def _split_by_window(self):
        try:
            action_log.info("按窗口拆分 script=%s events=%d", self._current_script_name, len(self._current_events))
            if not self._current_events and self._current_script_name:
                data = self.sm.load(self._current_script_name)
                if data:
                    self._current_events = data.get("events", [])
            if not self._current_events:
                messagebox.showinfo("提示", "没有可拆分的步骤")
                return
            pid_names = {}
            data = self.sm.load(self._current_script_name) if self._current_script_name else None
            if data:
                pid_names = data.get("meta", {}).get("pid_names", {})
            chain = self._build_logic_chain(self._current_events, pid_names, skip_ocr=True)
            blacklist = self._load_window_blacklist()
            raw_sections = []
            current_window = ""
            current_steps = []
            for step in chain:
                if step.get("type") == "switch_window":
                    if current_steps:
                        raw_sections.append((current_window, current_steps))
                    current_window = step.get("target", "")
                    current_steps = []
                else:
                    current_steps.append(step)
            if current_steps:
                raw_sections.append((current_window, current_steps))
            window_ranges = {}
            window_order = []
            for window, steps in raw_sections:
                win_short = window.split(" - ")[0].strip() if window else "未命名"
                if any(b in win_short for b in blacklist):
                    continue
                idx_list = [s["event_idx"] for s in steps if "event_idx" in s and 0 <= s["event_idx"] < len(self._current_events)]
                if not idx_list:
                    continue
                if win_short not in window_ranges:
                    window_ranges[win_short] = []
                    window_order.append(win_short)
                window_ranges[win_short].append((min(idx_list), max(idx_list) + 1))
            if len(window_ranges) <= 1:
                messagebox.showinfo("提示", "只有一个窗口，无需拆分")
                return
            window_names = ", ".join(window_order)
            base_name = self._current_script_name or "script"
            saved = 0
            sub_results = []
            for win_short in window_order:
                sub_name = f"{base_name}_{win_short}"
                sub_events = []
                for start, end in window_ranges[win_short]:
                    sub_events.extend(self._current_events[start:end])
                if sub_events:
                    sub_chain = self._build_logic_chain(sub_events, pid_names, skip_ocr=True)
                    sub_intent = self._logic_chain_to_intent(sub_chain)
                    self.sm.save(sub_name, sub_events, {"pid_names": pid_names}, intent=sub_intent)
                    saved += 1
                    sub_results.append((sub_name, len(sub_events), sub_chain))
            self._refresh_scripts()
            self.status_var.set(f"已拆分为 {saved} 个子脚本: {window_names}")
            for sub_name, evt_count, sub_chain in sub_results:
                top = tk.Toplevel(self.root)
                top.title(f"拆分校准: {sub_name}")
                top.geometry("900x550")
                top.transient(self.root)
                ttk.Label(top, text=f"{sub_name} ({evt_count} 步) - 点击步骤查看截图，双击修正文本", font=("", 10, "bold")).pack(padx=8, pady=(8, 2), anchor=tk.W)
                pane = ttk.PanedWindow(top, orient=tk.HORIZONTAL)
                pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
                left = ttk.Frame(pane)
                pane.add(left, weight=3)
                right = ttk.LabelFrame(pane, text="截图预览")
                pane.add(right, weight=1)
                pv_label = ttk.Label(right, text="点击步骤查看截图", wraplength=250)
                pv_label.pack(padx=4, pady=4)
                pv_img = ttk.Label(right)
                pv_img.pack(padx=4, pady=4)
                cols = ("step", "ocr", "screenshot")
                tree = ttk.Treeview(left, columns=cols, show="headings", height=18)
                tree.heading("step", text="步骤")
                tree.heading("ocr", text="识别文本")
                tree.heading("screenshot", text="截图")
                tree.column("step", width=250)
                tree.column("ocr", width=180)
                tree.column("screenshot", width=50)
                sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=sb.set)
                sb.pack(side=tk.RIGHT, fill=tk.Y)
                tree.pack(fill=tk.BOTH, expand=True)
                sd_list = []
                for step in sub_chain:
                    st = step.get("type", "")
                    if st == "switch_window":
                        desc = f"[切换] {step.get('target', '')}"
                        ocr = ""
                    elif st == "click":
                        desc = f"点击{step.get('desc', '')}"
                        ocr = step.get("ocr", "") or step.get("desc", "")
                    elif st == "input":
                        desc = f"输入[{step.get('text', '')}]"
                        ocr = step.get("text", "")
                    elif st == "keypress":
                        desc = f"按{step.get('key', '')}"
                        ocr = step.get("key", "")
                    elif st == "scroll":
                        desc = f"{step.get('direction', '')}滚动"
                        ocr = ""
                    else:
                        continue
                    ss = step.get("screenshot_path", "")
                    has_ss = "有" if ss else ""
                    iid = tree.insert("", tk.END, values=(desc, ocr, has_ss))
                    sd_list.append({"iid": iid, "ocr": ocr, "screenshot_path": ss})
                def _sel(e=None, sd_list=sd_list, pv_label=pv_label, pv_img=pv_img, tree=tree):
                    sel = tree.selection()
                    if not sel:
                        return
                    for sd in sd_list:
                        if sd["iid"] == sel[0]:
                            ss = sd.get("screenshot_path", "")
                            if ss and os.path.exists(ss):
                                try:
                                    from PIL import Image, ImageTk
                                    img = Image.open(ss)
                                    img.thumbnail((250, 250))
                                    photo = ImageTk.PhotoImage(img)
                                    pv_img.configure(image=photo)
                                    pv_img.image = photo
                                    pv_label.configure(text=sd.get("ocr", ""))
                                except Exception:
                                    pv_label.configure(text="截图加载失败")
                            else:
                                pv_img.configure(image="")
                                pv_label.configure(text="无截图")
                            break
                tree.bind("<<TreeviewSelect>>", _sel)
                btn_frame = ttk.Frame(top)
                btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
                ttk.Button(btn_frame, text="关闭", command=top.destroy).pack(side=tk.RIGHT)
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("拆分错误", str(e))

    def _load_window_blacklist(self):
        bl_path = os.path.join(self._scripts_dir, "window_blacklist.txt")
        if os.path.exists(bl_path):
            with open(bl_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def _edit_window_blacklist(self):
        bl_path = os.path.join(self._scripts_dir, "window_blacklist.txt")
        current = self._load_window_blacklist()
        top = tk.Toplevel(self.root)
        top.title("窗口黑名单 - 拆分时排除的窗口")
        top.geometry("400x220")
        top.resizable(False, False)
        top.transient(self.root)
        ttk.Label(top, text="每行一个窗口名(部分匹配)，拆分时自动排除:", font=("", 10)).pack(padx=8, pady=(8, 2), anchor=tk.W)
        txt = tk.Text(top, wrap=tk.WORD, font=("", 11), height=5)
        txt.pack(fill=tk.X, padx=8, pady=4)
        txt.insert("1.0", "\n".join(current))
        btn = ttk.Frame(top)
        btn.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(btn, text="保存并关闭", command=lambda: (self._save_blacklist(bl_path, txt), top.destroy())).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn, text="取消", command=top.destroy).pack(side=tk.RIGHT, padx=4)

    def _save_blacklist(self, bl_path, txt_widget):
        lines = txt_widget.get("1.0", tk.END).strip().split("\n")
        with open(bl_path, "w", encoding="utf-8") as f:
            f.write("\n".join(l.strip() for l in lines if l.strip()))
        self.status_var.set(f"黑名单已保存: {bl_path}")

    def _save_intent_text(self):
        action_log.info("保存逻辑链条")
        text = self.intent_text.get("1.0", tk.END).strip()
        if not text or not self._current_script_name:
            return
        path = os.path.join(self._scripts_dir, "scripts", f"{self._current_script_name}_logic.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.status_var.set(f"逻辑链条已保存: {path}")

    def _popup_intent_editor(self):

        try:
            sync_log.debug("弹出OCR校验编辑器")
            if not self._current_events and self._current_script_name:
                data = self.sm.load(self._current_script_name)
                if data:
                    self._current_events = data.get("events", [])
            if not self._current_events:
                messagebox.showinfo("提示", "没有可编辑的步骤")
                return
            pid_names = {}
            data = self.sm.load(self._current_script_name) if self._current_script_name else None
            if data:
                pid_names = data.get("meta", {}).get("pid_names", {})
            chain = self._build_logic_chain(self._current_events, pid_names, skip_ocr=True)

            top = tk.Toplevel(self.root)
            top.title("OCR校验编辑器 - 截图+识别对照")
            top.geometry("1000x700")
            top.transient(self.root)

            toolbar = ttk.Frame(top)
            toolbar.pack(fill=tk.X, padx=4, pady=4)
            ttk.Label(toolbar, text="修正OCR识别错误，保存后自动学习到修正库", foreground="#2563eb", font=("", 10, "bold")).pack(side=tk.LEFT, padx=4)

            main_pane = ttk.PanedWindow(top, orient=tk.HORIZONTAL)
            main_pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

            left_frame = ttk.Frame(main_pane)
            main_pane.add(left_frame, weight=3)

            right_frame = ttk.LabelFrame(main_pane, text="截图预览")
            main_pane.add(right_frame, weight=1)

            preview_label = ttk.Label(right_frame, text="点击左侧步骤查看截图", wraplength=250)
            preview_label.pack(padx=4, pady=4)
            preview_img_label = ttk.Label(right_frame)
            preview_img_label.pack(padx=4, pady=4)

            cols = ("step", "original", "corrected", "screenshot")
            tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=20)
            tree.heading("step", text="步骤")
            tree.heading("original", text="原始识别")
            tree.heading("corrected", text="修正文本")
            tree.heading("screenshot", text="截图")
            tree.column("step", width=200)
            tree.column("original", width=150)
            tree.column("corrected", width=150)
            tree.column("screenshot", width=60)

            tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            tree.pack(fill=tk.BOTH, expand=True)

            step_data = []
            for i, step in enumerate(chain):
                stype = step.get("type", "")
                if stype == "switch_window":
                    desc = f"[切换] {step.get('target', '')}"
                    orig = ""
                elif stype == "click":
                    desc = f"点击{step.get('desc', '')}"
                    orig = step.get("ocr", "") or step.get("desc", "")
                elif stype == "input":
                    desc = f"输入[{step.get('text', '')}]"
                    orig = step.get("text", "")
                elif stype == "keypress":
                    desc = f"按{step.get('key', '')}"
                    orig = step.get("key", "")
                elif stype == "scroll":
                    desc = f"{step.get('direction', '')}滚动"
                    orig = ""
                else:
                    continue
                count = step.get("_count", 1)
                if count > 1:
                    desc += f" x{count}"
                ss_path = step.get("screenshot_path", "")
                has_ss = "有" if ss_path else ""
                iid = tree.insert("", tk.END, values=(desc, orig, orig, has_ss))
                step_data.append({"iid": iid, "step": step, "original": orig, "screenshot_path": ss_path})

            def _on_select(event=None):
                sel = tree.selection()
                if not sel:
                    return
                iid = sel[0]
                for sd in step_data:
                    if sd["iid"] == iid:
                        ss = sd.get("screenshot_path", "")
                        if ss and os.path.exists(ss):
                            try:
                                from PIL import Image, ImageTk
                                img = Image.open(ss)
                                img.thumbnail((250, 250))
                                photo = ImageTk.PhotoImage(img)
                                preview_img_label.configure(image=photo)
                                preview_img_label.image = photo
                                preview_label.configure(text=sd.get("original", ""))
                            except Exception:
                                preview_label.configure(text=f"截图加载失败")
                        else:
                            preview_img_label.configure(image="")
                            preview_label.configure(text="无截图")
                        break

            tree.bind("<<TreeviewSelect>>", _on_select)

            def _on_double_click(event=None):
                sel = tree.selection()
                if not sel:
                    return
                iid = sel[0]
                col = tree.identify_column(event.x)
                if col == "#3":
                    bbox = tree.bbox(iid, col)
                    if not bbox:
                        return
                    entry = tk.Entry(tree)
                    entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
                    current = tree.set(iid, "corrected")
                    entry.insert(0, current)
                    entry.select_range(0, tk.END)
                    entry.focus_set()

                    def _save_edit(e=None):
                        new_val = entry.get()
                        tree.set(iid, "corrected", new_val)
                        entry.destroy()

                    entry.bind("<Return>", _save_edit)
                    entry.bind("<Escape>", lambda e: entry.destroy())
                    entry.bind("<FocusOut>", _save_edit)

            tree.bind("<Double-1>", _on_double_click)

            def _apply_and_learn():
                corrections = []
                for sd in step_data:
                    original = tree.set(sd["iid"], "original")
                    corrected = tree.set(sd["iid"], "corrected")
                    if corrected and corrected != original:
                        corrections.append({
                            "original": original,
                            "corrected": corrected,
                            "screenshot_path": sd.get("screenshot_path", ""),
                        })
                if corrections:
                    try:
                        from ocr_corrections import record_correction
                        for c in corrections:
                            if c["screenshot_path"]:
                                record_correction(c["screenshot_path"], c["original"], c["corrected"])
                        self.status_var.set(f"已学习 {len(corrections)} 条OCR修正")
                    except Exception as ex:
                        logger.warning("OCR修正保存失败: %s", ex)
                top.destroy()

            btn_frame = ttk.Frame(top)
            btn_frame.pack(fill=tk.X, padx=4, pady=4)
            ttk.Button(btn_frame, text="应用并学习修正", command=_apply_and_learn, width=14).pack(side=tk.LEFT, padx=4)
            ttk.Label(btn_frame, text="双击[修正文本]列可编辑", foreground="#999").pack(side=tk.LEFT, padx=8)
            ttk.Button(btn_frame, text="关闭", command=top.destroy, width=8).pack(side=tk.RIGHT, padx=4)
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("编辑器错误", str(e))

    def _ai_optimize_intent(self):
        action_log.info("AI优化逻辑链条")
        if not self._current_script_name:
            return
        data = self.sm.load(self._current_script_name)
        if not data:
            return
        events = data.get("events", [])
        meta = data.get("meta", {})
        self.status_var.set("AI优化逻辑链条中...")
        self.root.update_idletasks()
        try:
            import ai_recognizer
            intent = ai_recognizer.generate_intent_with_fallback(events, meta)
            if intent:
                self.intent_text.delete("1.0", tk.END)
                self.intent_text.insert("1.0", intent)
                self.status_var.set("AI优化完成")
            else:
                self.status_var.set("AI优化失败（未配置API Key？）")
        except Exception as e:
            logger.warning("AI优化失败: %s", e)
            self.status_var.set(f"AI优化失败: {e}")

    def _ask_skill_params(self, script_name, params):
        top = tk.Toplevel(self.root)
        top.title(f"⚡ Skill参数: {script_name}")
        top.geometry("400x300")
        top.transient(self.root)
        top.grab_set()
        result = [None]

        frm = ttk.Frame(top, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text=f"执行Skill: {script_name}", font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

        entries = {}
        for p in params:
            row = ttk.Frame(frm)
            row.pack(fill=tk.X, pady=3)
            label = p.get("desc", p.get("name", ""))
            ttk.Label(row, text=f"{label}:").pack(side=tk.LEFT, padx=(0, 4))
            var = tk.StringVar(value="")
            ttk.Entry(row, textvariable=var, width=25).pack(side=tk.LEFT, fill=tk.X, expand=True)
            entries[p.get("name", "")] = var

        if not params:
            ttk.Label(frm, text="此Skill无需参数", foreground="#999").pack(anchor="w")

        def _confirm():
            vals = {}
            for name, var in entries.items():
                v = var.get().strip()
                if v:
                    vals[name] = v
            result[0] = vals
            top.destroy()

        def _cancel():
            top.destroy()

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="执行", command=_confirm, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=_cancel, width=8).pack(side=tk.RIGHT)

        top.wait_window()
        return result[0]

    def _update_ai_status(self):
        try:
            import ai_recognizer
            status = ai_recognizer.get_ai_status()
            if status["online"]:
                parts = ["[在线]在线"]
                if status["cloud_vision"]:
                    parts.append("视觉AI")
                if status["cloud_text"]:
                    parts.append("文本AI")
                if status["local_trocr"]:
                    parts.append("TrOCR")
                self.ai_status_var.set(" ".join(parts))
            else:
                parts = ["[离网]离网"]
                if status["local_trocr"]:
                    parts.append("TrOCR")
                parts.append("本地OCR")
                self.ai_status_var.set(" ".join(parts))
        except Exception:
            self.ai_status_var.set("")
        self.root.after(30000, self._update_ai_status)


    def _nl_execute(self):
        query = self.script_search_var.get().strip()
        if not query:
            self._refresh_scripts()
            return
        matches = self.sm.match_skill(query)
        if not matches:
            if messagebox.askyesno("未找到匹配Skill",
                f"没有匹配「{query}」的Skill。\n\n是否用AI创建新脚本？"):
                self._ai_create_script(query)
            else:
                self._search_scripts()
            return
        best = matches[0]
        name = best["name"]
        if len(matches) > 1:
            names = [m["name"] for m in matches[:5]]
            if not messagebox.askyesno("匹配到多个Skill",
                f"最佳匹配: {name}\n\n其他匹配: {', '.join(names[1:])}\n\n是否执行「{name}」？"):
                self._search_scripts()
                return
        self.status_var.set(f"执行Skill: {name}")
        self._play_by_name(name)

    def _play_by_name(self, name, params_override=None):
        data = self.sm.load(name)
        if not data:
            messagebox.showerror("错误", f"脚本不存在: {name}")
            return
        events = [e for e in data.get("events", []) if not e.get("disabled")]
        if not events:
            messagebox.showwarning("提示", f"脚本「{name}」没有可用步骤")
            return
        speed = self.speed_var.get()
        pids = [e.get("pid") for e in events if e.get("pid")]
        target_pid = Counter(pids).most_common(1)[0][0] if pids else None
        data_source = data.get("meta", {}).get("data_source")
        has_variables = any(e.get("variable") for e in events)

        skill_meta = data.get("skill_meta", {})
        skill_params = skill_meta.get("params", [])
        user_vars = params_override or {}
        if skill_params and not user_vars:
            user_vars = self._ask_skill_params(name, skill_params)
            if user_vars is None:
                return

        engine_type = skill_meta.get("engine", "auto")
        browser_profile = skill_meta.get("browser_profile")
        browser_engine = getattr(self, '_browser_engine', None)

        if engine_type in ("browser", "browser_dom") and browser_engine and browser_engine.is_connected():
            if browser_profile and browser_profile not in [s["id"] for s in getattr(self, '_browser_sessions', [])]:
                sid, page = browser_engine.new_identity(headless=False)
                if sid:
                    self._browser_sessions.append({"id": sid, "page": page})
                    browser_profile = sid
            elif not browser_profile:
                browser_profile = browser_engine.get_active_session_id()

        self.player = Player(speed=speed, target_pid=target_pid, smart_replay=self.smart_replay_var.get(),
                             visual_match=self.visual_match_var.get(), scripts_dir=self._scripts_dir,
                             retry_count=3, on_error="continue",
                             use_ai_fallback=self.ai_fallback_var.get(),
                             browser_engine=browser_engine if engine_type in ("browser", "browser_dom", "auto") else None,
                             browser_profile=browser_profile)
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
            self.player.play(events, variables=user_vars, data_source=ds_info)
            self.root.after(0, self._on_play_done, name)

        threading.Thread(target=run, daemon=True).start()

    def _init_scheduler(self):
        try:
            from scheduler import Scheduler
            self._scheduler = Scheduler()
            self._scheduler.start(on_trigger=self._scheduler_trigger)
        except Exception as e:
            logger.warning("调度器初始化失败: %s", e)
        try:
            from event_watcher import EventWatcher
            self._event_watcher = EventWatcher(on_trigger=self._scheduler_trigger)
            self._event_watcher.start()
        except Exception as e:
            logger.warning("事件监视器初始化失败: %s", e)
        self._load_skill_hotkeys()

    def _scheduler_trigger(self, script_name, params=None):
        logger.info("定时触发: %s", script_name)
        self.root.after(0, lambda: self._play_by_name(script_name, params))

    def _load_skill_hotkeys(self):
        self._skill_hotkeys = {}
        for s in self.sm.list_all():
            data = self.sm.load(s["name"])
            if data:
                sm = data.get("skill_meta", {})
                hk = sm.get("hotkey", "")
                if hk:
                    self._skill_hotkeys[hk.lower()] = s["name"]

    def _build_scheduler_tab(self):
        for w in self.scheduler_tab.winfo_children():
            w.destroy()

        top = ttk.Frame(self.scheduler_tab)
        top.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(top, text="定时任务", font=("", 11, "bold")).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(top, text="添加", command=self._scheduler_add, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="刷新", command=self._build_scheduler_tab, width=6).pack(side=tk.LEFT, padx=2)

        cols = ("script", "cron", "enabled", "last_run", "next_run")
        self.sched_tree = ttk.Treeview(self.scheduler_tab, columns=cols, show="headings", height=8)
        self.sched_tree.heading("script", text="脚本")
        self.sched_tree.heading("cron", text="定时表达式")
        self.sched_tree.heading("enabled", text="启用")
        self.sched_tree.heading("last_run", text="上次执行")
        self.sched_tree.heading("next_run", text="下次执行")
        self.sched_tree.column("script", width=150)
        self.sched_tree.column("cron", width=150)
        self.sched_tree.column("enabled", width=40)
        self.sched_tree.column("last_run", width=130)
        self.sched_tree.column("next_run", width=130)
        self.sched_tree.pack(fill=tk.BOTH, expand=True)

        action_row = ttk.Frame(self.scheduler_tab)
        action_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(action_row, text="立即执行", command=self._scheduler_run_now, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_row, text="启用/禁用", command=self._scheduler_toggle, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_row, text="删除", command=self._scheduler_delete, width=8).pack(side=tk.LEFT, padx=2)

        if self._scheduler:
            jobs = self._scheduler.list_jobs()
            for jid, job in jobs.items():
                enabled_text = "Y" if job.get("enabled", True) else "N"
                next_run = job.get("next_run", "")
                if isinstance(next_run, (int, float)):
                    import time as _t
                    next_run = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(next_run)) if next_run else ""
                self.sched_tree.insert("", tk.END, iid=jid,
                    values=(job.get("script_name", ""), job.get("cron_expr", ""),
                            enabled_text, job.get("last_run", "-"), next_run or "-"))

    def _scheduler_add(self):
        action_log.info("添加定时任务")
        scripts = self.sm.list_all()
        if not scripts:
            messagebox.showwarning("提示", "没有可用的脚本")
            return
        names = [s["name"] for s in scripts]

        top = tk.Toplevel(self.root)
        top.title("添加定时任务")
        top.geometry("400x200")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="脚本:").pack(anchor="w", pady=(0, 4))
        script_var = tk.StringVar()
        ttk.Combobox(frm, textvariable=script_var, values=names, width=30, state="readonly").pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frm, text="定时表达式:").pack(anchor="w", pady=(0, 4))
        cron_var = tk.StringVar(value="30m")
        cron_entry = ttk.Entry(frm, textvariable=cron_var, width=30)
        cron_entry.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(frm, text="支持: 30m=每30分钟, 2h=每2小时, 1d=每天\n或cron格式: */30 * * * *", foreground="#999").pack(anchor="w")

        def _add():
            sn = script_var.get().strip()
            ce = cron_var.get().strip()
            if not sn or not ce:
                return
            self._scheduler.add_job(sn, ce)
            top.destroy()
            self._build_scheduler_tab()
            self.status_var.set(f"已添加定时任务: {sn} ({ce})")

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="添加", command=_add, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _scheduler_run_now(self):
        sel = self.sched_tree.selection()
        if not sel:
            return
        jid = sel[0]
        job = self._scheduler.list_jobs().get(jid)
        if job:
            self._play_by_name(job["script_name"], job.get("params", {}))

    def _scheduler_toggle(self):
        sel = self.sched_tree.selection()
        if not sel:
            return
        jid = sel[0]
        self._scheduler.toggle_job(jid)
        self._build_scheduler_tab()

    def _scheduler_delete(self):
        action_log.info("删除定时任务")
        sel = self.sched_tree.selection()
        if not sel:
            return
        jid = sel[0]
        if messagebox.askyesno("确认", "删除此定时任务？"):
            self._scheduler.remove_job(jid)
            self._build_scheduler_tab()



    def _ai_create_script(self, description):
        action_log.info("AI创建脚本")
        self.status_var.set("AI创建脚本中...")
        self.root.update_idletasks()
        try:
            import ai_recognizer
            events = ai_recognizer.generate_script_from_description(description)
            if not events:
                self.status_var.set("AI创建脚本失败（未配置API Key或生成失败）")
                messagebox.showwarning("AI创建失败", "无法生成脚本。请检查AI配置或手动录制。")
                return
            import re
            name = "ai_" + re.sub(r'[\s\/:*?"<>|]+', '_', description[:20]).strip('_')
            name = name or "ai_script"
            meta = {"pid_names": {}, "logic_chain": []}
            intent = description
            skill_meta = self.sm.auto_generate_skill_meta(events, meta, intent)
            skill_meta["triggers"] = [description[:10]]
            self.sm.save(name, events, meta, intent=intent, skill_meta=skill_meta)
            self._refresh_scripts()
            self.status_var.set(f"AI创建脚本成功: {name} ({len(events)}步)")
            if messagebox.askyesno("AI脚本已创建",
                f"脚本「{name}」已创建 ({len(events)}步)\n\n是否立即执行？"):
                self._play_by_name(name)
        except Exception as e:
            self.status_var.set(f"AI创建脚本失败: {e}")
            logger.error("AI创建脚本失败: %s", e)

    def _build_watcher_tab(self):
        for w in self.watcher_tab.winfo_children():
            w.destroy()

        top = ttk.Frame(self.watcher_tab)
        top.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(top, text="事件触发", font=("", 11, "bold")).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(top, text="添加", command=self._watcher_add, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="刷新", command=self._build_watcher_tab, width=6).pack(side=tk.LEFT, padx=2)

        cols = ("type", "pattern", "script", "enabled", "last_triggered")
        self.watch_tree = ttk.Treeview(self.watcher_tab, columns=cols, show="headings", height=8)
        self.watch_tree.heading("type", text="类型")
        self.watch_tree.heading("pattern", text="匹配条件")
        self.watch_tree.heading("script", text="脚本")
        self.watch_tree.heading("enabled", text="启用")
        self.watch_tree.heading("last_triggered", text="上次触发")
        self.watch_tree.column("type", width=80)
        self.watch_tree.column("pattern", width=200)
        self.watch_tree.column("script", width=150)
        self.watch_tree.column("enabled", width=40)
        self.watch_tree.column("last_triggered", width=130)
        self.watch_tree.pack(fill=tk.BOTH, expand=True)

        action_row = ttk.Frame(self.watcher_tab)
        action_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(action_row, text="启用/禁用", command=self._watcher_toggle, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_row, text="删除", command=self._watcher_delete, width=8).pack(side=tk.LEFT, padx=2)

        type_names = {"file": "文件", "clipboard": "剪贴板", "window": "窗口"}
        if self._event_watcher:
            watchers = self._event_watcher.list_watchers()
            for wid, w in watchers.items():
                enabled_text = "Y" if w.get("enabled", True) else "N"
                tname = type_names.get(w.get("type", ""), w.get("type", ""))
                self.watch_tree.insert("", tk.END, iid=wid,
                    values=(tname, w.get("pattern", ""), w.get("script_name", ""),
                            enabled_text, w.get("last_triggered", "-")))

    def _watcher_add(self):
        action_log.info("添加事件监视")
        scripts = self.sm.list_all()
        if not scripts:
            messagebox.showwarning("提示", "没有可用的脚本")
            return
        names = [s["name"] for s in scripts]

        top = tk.Toplevel(self.root)
        top.title("添加事件触发")
        top.geometry("420x250")
        top.transient(self.root)
        top.grab_set()

        frm = ttk.Frame(top, padding=15)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="触发类型:").pack(anchor="w", pady=(0, 4))
        type_var = tk.StringVar(value="file")
        type_combo = ttk.Combobox(frm, textvariable=type_var,
            values=["file", "clipboard", "window"], width=15, state="readonly")
        type_combo.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frm, text="匹配条件:").pack(anchor="w", pady=(0, 4))
        pattern_var = tk.StringVar()
        ttk.Entry(frm, textvariable=pattern_var, width=40).pack(fill=tk.X, pady=(0, 4))
        ttk.Label(frm, text="文件=路径, 剪贴板=关键词, 窗口=窗口名", foreground="#999").pack(anchor="w", pady=(0, 8))

        ttk.Label(frm, text="执行脚本:").pack(anchor="w", pady=(0, 4))
        script_var = tk.StringVar()
        ttk.Combobox(frm, textvariable=script_var, values=names, width=30, state="readonly").pack(fill=tk.X)

        def _add():
            wt = type_var.get().strip()
            pat = pattern_var.get().strip()
            sn = script_var.get().strip()
            if not wt or not sn:
                return
            self._event_watcher.add_watcher(wt, pat, sn)
            top.destroy()
            self._build_watcher_tab()
            self.status_var.set(f"已添加事件触发: {wt} -> {sn}")

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frm, text="添加", command=_add, width=8).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frm, text="取消", command=top.destroy, width=8).pack(side=tk.RIGHT)

    def _watcher_toggle(self):
        sel = self.watch_tree.selection()
        if not sel:
            return
        wid = sel[0]
        self._event_watcher.toggle_watcher(wid)
        self._build_watcher_tab()

    def _watcher_delete(self):
        action_log.info("删除事件监视")
        sel = self.watch_tree.selection()
        if not sel:
            return
        wid = sel[0]
        if messagebox.askyesno("确认", "删除此事件触发规则？"):
            self._event_watcher.remove_watcher(wid)
            self._build_watcher_tab()


    def _check_permissions(self):
        sync_log.debug("检查权限")
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

    def _build_browser_tab(self):
        for w in self.browser_tab.winfo_children():
            w.destroy()

        try:
            from browser_engine import BrowserEngine
            self._browser_engine = BrowserEngine()
            self._browser_available = self._browser_engine.is_available()
        except ImportError:
            self._browser_engine = None
            self._browser_available = False

        action_frame = ttk.Frame(self.browser_tab)
        action_frame.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(action_frame, text="[浏览器] 打开新浏览器", command=self._browser_open_new, width=16).pack(side=tk.LEFT, padx=4)
        ttk.Button(action_frame, text="[循环] 连接已有浏览器", command=self._browser_connect_cdp, width=16).pack(side=tk.LEFT, padx=4)

        if not self._browser_available:
            ttk.Label(action_frame, text="（需安装: pip install playwright && playwright install chromium）",
                      foreground="#999").pack(side=tk.LEFT, padx=8)

        self._sessions_frame = ttk.LabelFrame(self.browser_tab, text="已打开的浏览器身份")
        self._sessions_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._browser_sessions = []
        self._refresh_browser_sessions()

        tip_frame = ttk.Frame(self.browser_tab)
        tip_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(tip_frame, text="[提示] 每点一次「打开新浏览器」= 一个全新身份（独立Cookie/指纹/登录状态）\n"
                                   "登录不同账号用不同浏览器，互不干扰，网站无法识别是同一台电脑。",
                  foreground="#666", wraplength=600, justify="left").pack(anchor="w", padx=4)

    def _browser_open_new(self):
        action_log.info("打开浏览器")
        if not self._browser_engine:
            messagebox.showwarning("提示", "Playwright未安装\n\npip install playwright\nplaywright install chromium")
            return
        if not self._browser_engine._check_chromium():
            self.status_var.set("正在下载Chromium核心，请稍候...")
            self.root.update()
            if not self._browser_engine._install_chromium():
                messagebox.showerror("错误", "Chromium下载失败，请检查网络连接")
                self.status_var.set("就绪")
                return
            self.status_var.set("Chromium安装完成，正在启动...")
            self.root.update()
        session_id, page = self._browser_engine.new_identity(headless=False)
        if page:
            self._browser_sessions.append({"id": session_id, "page": page})
            self._refresh_browser_sessions()
            self.status_var.set(f"浏览器身份 {session_id} 已启动")
        else:
            messagebox.showerror("错误", "浏览器启动失败")

    def _browser_connect_cdp(self):
        action_log.info("连接CDP")
        if not self._browser_engine:
            messagebox.showwarning("提示", "Playwright未安装")
            return
        url = _ask_string(self.root, "连接已有浏览器", "浏览器调试地址:", "http://localhost:9222")
        if not url:
            return
        result = self._browser_engine.connect_cdp(url)
        if result:
            self._browser_sessions.append({"id": f"cdp-{len(self._browser_sessions)}", "page": None})
            self._refresh_browser_sessions()
        else:
            messagebox.showerror("错误", "连接失败，请确认浏览器已开启远程调试")

    def _browser_close_session(self, session_id):
        action_log.info("关闭浏览器会话")
        if self._browser_engine:
            self._browser_engine.close_identity(session_id)
        self._browser_sessions = [s for s in self._browser_sessions if s["id"] != session_id]
        self._refresh_browser_sessions()

    def _refresh_browser_sessions(self):
        if not hasattr(self, '_sessions_frame'):
            return
        for w in self._sessions_frame.winfo_children():
            w.destroy()
        if not self._browser_sessions:
            ttk.Label(self._sessions_frame, text="暂无浏览器身份，点击上方「打开新浏览器」开始",
                      foreground="#999").pack(padx=4, pady=8)
            return
        for s in self._browser_sessions:
            row = ttk.Frame(self._sessions_frame)
            row.pack(fill=tk.X, padx=4, pady=2)
            url = ""
            try:
                url = s.get("page").url if s.get("page") else ""
            except Exception:
                pass
            url_display = url[:50] + "..." if len(url) > 50 else url
            ttk.Label(row, text=f"[用户] {s['id']}", font=("", 10, "bold")).pack(side=tk.LEFT, padx=4)
            if url_display:
                ttk.Label(row, text=url_display, foreground="#888").pack(side=tk.LEFT, padx=4)
            ttk.Button(row, text="关闭", command=lambda sid=s["id"]: self._browser_close_session(sid),
                       width=6).pack(side=tk.RIGHT, padx=4)

    def _start_hotkey_listener(self):
        sync_log.debug("启动快捷键监听")
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
        action_log.info("快捷键切换录制")
        if self.recording:
            self._stop_record()
        elif not self.playing:
            self._start_record_silent()

    def _hotkey_stop(self):
        action_log.info("快捷键停止")
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
        sync_log.debug("关闭窗口")
        if self.recording:
            self._stop_record()
        if self.playing:
            self._stop_play()
        if hasattr(self, '_scheduler') and self._scheduler:
            self._scheduler.stop()
        if hasattr(self, '_event_watcher') and self._event_watcher:
            self._event_watcher.stop()
        if hasattr(self, '_visual_editor') and self._visual_editor:
            try:
                if self._visual_editor._process:
                    self._visual_editor._process.kill()
                    sync_log.debug("已关闭可视化编辑器子进程 PID=%d", self._visual_editor._process.pid)
            except Exception:
                pass
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
        ttk.Button(search_frame, text="[搜索] 搜索", command=self._market_search, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Button(search_frame, text="[滚动] 刷新", command=self._market_refresh, width=8).pack(side=tk.LEFT, padx=4)

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
        ttk.Button(action_frame, text="[下载] 下载", command=self._market_download, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="[分支] 智能合并", command=self._market_merge, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="[列表] 详情", command=self._market_detail, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Separator(action_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(action_frame, text="[上传] 共享到GitHub", command=self._share_script, width=14).pack(side=tk.LEFT, padx=3)

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
                "[文件] 本地",
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
        action_log.info("下载脚本 entry=%s", entry.get("name", "?"))
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
        action_log.info("合并脚本")
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
            detail += "来源: [文件] 本地\n"
        else:
            entry = self._get_selected_market_script()
            if entry:
                detail += f"来源: [浏览器] 远程\n"
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
        action_log.info("分享脚本 name=%s", self._current_script_name)
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
