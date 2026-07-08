import time
import logging
import os
import subprocess
import threading
import ctypes
import ctypes.wintypes
from ctypes import windll, byref, sizeof, Structure, POINTER

logger = logging.getLogger("win_player")

user32 = windll.user32

OCR_REGION_SIZE = 200
TEMPLATE_MATCH_THRESHOLD = 0.55

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MODIFIER_VK = {
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
}

FUNCTION_VK = set(range(0x70, 0x7C)) | {0x08, 0x09, 0x0D, 0x1B, 0x20, 0x2E, 0x24, 0x23, 0x21, 0x22}


class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR),
    ]


class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", INPUT_UNION)]


def _send_input(*inputs):
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    user32.SendInput(n, byref(arr), sizeof(INPUT))


def _make_mouse_input(x, y, flags, data=0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = x
    inp.union.mi.dy = y
    inp.union.mi.mouseData = data
    inp.union.mi.dwFlags = flags
    return inp


def _make_key_input(vk, flags=0):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = flags
    return inp


def _activate_app(pid):
    try:
        hwnd = ctypes.wintypes.HWND()
        result = [None]

        def enum_cb(h, _):
            p = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, byref(p))
            if p.value == pid and user32.IsWindowVisible(h):
                result[0] = h
                return False
            return True

        CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(CB(enum_cb), 0)
        if result[0]:
            user32.SetForegroundWindow(result[0])
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False


def ocr_find_text(target_text, lang="chi_sim+eng", region=None):
    try:
        import mss
        import pytesseract
        from PIL import Image
        with mss.MSS() as sct:
            if region:
                screenshot = sct.grab(region)
            else:
                screenshot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        results = []
        search = target_text.lower() if target_text else None
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            if search and search not in text.lower():
                continue
            x = data["left"][i] + data["width"][i] // 2
            y = data["top"][i] + data["height"][i] // 2
            if region:
                x += region.get("left", 0)
                y += region.get("top", 0)
            results.append((x, y, text.strip()))
        return results
    except Exception:
        return []


def template_match(template_path, threshold=TEMPLATE_MATCH_THRESHOLD, multi_scale=True, window_bounds=None):
    try:
        import cv2
        import numpy as np
        import mss
        from PIL import Image
        if not os.path.exists(template_path):
            return None
        tpl_img = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if tpl_img is None:
            return None
        with mss.MSS() as sct:
            screenshot = sct.grab(sct.monitors[1])
            screen_img = np.array(Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"))
        screen_bgr = cv2.cvtColor(screen_img, cv2.COLOR_RGB2BGR)

        if window_bounds:
            wx = max(0, int(window_bounds.get("x", 0)) - 20)
            wy = max(0, int(window_bounds.get("y", 0)) - 20)
            ww = int(window_bounds.get("width", screen_bgr.shape[1])) + 40
            wh = int(window_bounds.get("height", screen_bgr.shape[0])) + 40
            wx2 = min(screen_bgr.shape[1], wx + ww)
            wy2 = min(screen_bgr.shape[0], wy + wh)
            search_img = screen_bgr[wy:wy2, wx:wx2]
            offset_x, offset_y = wx, wy
        else:
            search_img = screen_bgr
            offset_x, offset_y = 0, 0

        best_val = 0
        best_loc = None
        best_size = None
        scales = [0.75, 0.875, 1.0, 1.125, 1.25] if multi_scale else [1.0]

        for scale in scales:
            if scale != 1.0:
                new_w = int(tpl_img.shape[1] * scale)
                new_h = int(tpl_img.shape[0] * scale)
                if new_w < 10 or new_h < 10 or new_w > search_img.shape[1] or new_h > search_img.shape[0]:
                    continue
                scaled_tpl = cv2.resize(tpl_img, (new_w, new_h))
            else:
                scaled_tpl = tpl_img
            result = cv2.matchTemplate(search_img, scaled_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_size = scaled_tpl.shape[:2]

        if best_val >= threshold and best_loc is not None:
            h, w = best_size
            center_x = best_loc[0] + w // 2 + offset_x
            center_y = best_loc[1] + h // 2 + offset_y
            return center_x, center_y, best_val
        return None
    except Exception as e:
        logger.warning("模板匹配异常: %s", e)
        return None


def _paste_text(text):
    try:
        import pyperclip
        old = pyperclip.paste()
    except Exception:
        old = ""
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception:
        return False
    time.sleep(0.02)
    _send_input(
        _make_key_input(0x11, 0),
        _make_key_input(0x56, 0),
        _make_key_input(0x56, KEYEVENTF_KEYUP),
        _make_key_input(0x11, KEYEVENTF_KEYUP),
    )
    time.sleep(0.05)
    try:
        import pyperclip
        pyperclip.copy(old)
    except Exception:
        pass
    return True


class WinPlayer:
    def __init__(self, speed=1.0, target_pid=None, smart_replay=False, visual_match=False, scripts_dir=None,
                 retry_count=3, retry_interval=1.0, global_timeout=300, on_error="retry"):
        self.speed = speed
        self.target_pid = target_pid
        self.smart_replay = smart_replay
        self.visual_match = visual_match
        self.scripts_dir = scripts_dir
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.global_timeout = global_timeout
        self.on_error = on_error
        self._stop = False
        self._paused = threading.Event()
        self._paused.set()
        self._event_index = 0
        self._total_events = 0
        self._start_wall_time = None
        self._execution_log = []
        self._variables = {}

    def stop(self):
        self._stop = True

    def pause(self):
        self._paused.clear()

    def resume(self):
        self._paused.set()

    @property
    def progress(self):
        if self._total_events == 0:
            return 0
        return self._event_index / self._total_events

    @property
    def execution_log(self):
        return self._execution_log

    @property
    def variables(self):
        return dict(self._variables)

    def _resolve_var(self, value):
        if isinstance(value, str) and "{{" in value:
            import re
            def _replace(m):
                var_name = m.group(1).strip()
                return str(self._variables.get(var_name, m.group(0)))
            return re.sub(r"\{\{(.+?)\}\}", _replace, value)
        return value

    def _play_data_driven(self, events, data_source_info):
        import data_source as ds
        path = data_source_info.get("path", "")
        if not path or not os.path.exists(path):
            logger.error("数据源文件不存在: %s", path)
            return
        rows = ds.read_file(path)
        if not rows:
            logger.error("数据源为空: %s", path)
            return
        total_rows = len(rows)
        logger.info("数据驱动回放: %d 行数据, %d 步模板", total_rows, len(events))
        for row_idx, row in enumerate(rows):
            if self._stop:
                break
            logger.info("数据驱动: 第 %d/%d 行", row_idx + 1, total_rows)
            row_vars = dict(self._variables)
            row_vars.update(row)
            self._event_index = 0
            self.play(events, variables=row_vars, _recursive=True)
            if row_idx < total_rows - 1:
                time.sleep(1.0 / self.speed)
        logger.info("数据驱动回放完成: %d 行", total_rows)

    def play(self, events, variables=None, _recursive=False, data_source=None):
        self._stop = False
        self._paused.set()
        self._event_index = 0
        self._total_events = len(events)
        self._start_wall_time = time.time() if not _recursive else (self._start_wall_time or time.time())
        if not _recursive:
            self._execution_log = []
        self._variables = dict(variables) if variables else (self._variables if _recursive else {})
        if not events:
            return

        if not _recursive and data_source:
            self._play_data_driven(events, data_source)
            return

        if self.target_pid:
            _activate_app(self.target_pid)
            time.sleep(0.3)

        try:
            i = 0
            while i < len(events):
                if self._stop:
                    break
                if time.time() - self._start_wall_time > self.global_timeout:
                    logger.error("全局超时 (%ds)", self.global_timeout)
                    break
                self._paused.wait()
                event = events[i]
                self._event_index = i
                etype = event.get("type")

                if etype in ("if", "endif", "for", "endfor", "while", "endwhile",
                             "set_variable", "call_script", "comment", "ai_recognize", "wait_manual"):
                    i += 1
                    continue

                step_delay = {
                    "mouse_down": 0.3, "mouse_up": 0.05, "mouse_drag": 0.3,
                    "key_down": 0.1, "key_up": 0.05, "scroll": 0.3,
                    "type_text": 0.1, "screenshot": 0.05,
                }.get(etype, 0.2)
                time.sleep(step_delay / self.speed)
                self._execute(event)
                i += 1
        except Exception as e:
            logger.error("回放异常: %s", e)

    def _execute(self, event):
        etype = event.get("type")
        if etype == "mouse_down":
            self._do_mouse_down(event)
        elif etype == "mouse_up":
            self._do_mouse_up(event)
        elif etype == "mouse_drag":
            self._do_mouse_drag(event)
        elif etype == "scroll":
            self._do_scroll(event)
        elif etype == "key_down":
            self._do_key_down(event)
        elif etype == "key_up":
            self._do_key_up(event)
        elif etype == "type_text":
            self._do_type_text(event)

    def _resolve_coords(self, event):
        if "x" not in event:
            return 0, 0
        win_bounds = self._get_target_window_bounds(event)
        tpl_file = event.get("template")
        if tpl_file and self.scripts_dir:
            for subdir in ["scripts/templates", "templates"]:
                tpl_path = os.path.join(self.scripts_dir, subdir, tpl_file)
                if os.path.exists(tpl_path):
                    result = template_match(tpl_path, window_bounds=win_bounds)
                    if result:
                        new_x, new_y, confidence = result
                        logger.info("视觉匹配: %s 新=(%.0f,%.0f) 置信度=%.2f", tpl_file, new_x, new_y, confidence)
                        return new_x, new_y
                    break
        anchor = event.get("ocr_anchor")
        if anchor and len(anchor.get("text", "")) >= 2:
            target_text = anchor["text"]
            region = {
                "left": max(0, int(event["x"]) - OCR_REGION_SIZE),
                "top": max(0, int(event["y"]) - OCR_REGION_SIZE),
                "width": OCR_REGION_SIZE * 2,
                "height": OCR_REGION_SIZE * 2,
            }
            results = ocr_find_text(target_text, region=region)
            if results:
                best_x, best_y, _ = results[0]
                new_x = best_x - anchor["offset_x"]
                new_y = best_y - anchor["offset_y"]
                if 0 <= new_x <= 3000 and 0 <= new_y <= 2000:
                    return new_x, new_y
        return event["x"], event["y"]

    def _get_target_window_bounds(self, event):
        pid = event.get("pid") or self.target_pid
        if not pid:
            return None
        try:
            result = [None]
            def enum_cb(h, _):
                p = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, byref(p))
                if p.value == pid and user32.IsWindowVisible(h):
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(h, byref(rect))
                    result[0] = {"x": rect.left, "y": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}
                    return False
                return True
            CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            user32.EnumWindows(CB(enum_cb), 0)
            return result[0]
        except Exception:
            return None

    def _do_mouse_down(self, event):
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        pid = event.get("pid")
        if pid:
            _activate_app(pid)
            time.sleep(0.1)
        flags = {"left": MOUSEEVENTF_LEFTDOWN, "right": MOUSEEVENTF_RIGHTDOWN, "middle": MOUSEEVENTF_MIDDLEDOWN}.get(button, MOUSEEVENTF_LEFTDOWN)
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.02)
        _send_input(_make_mouse_input(x, y, flags))

    def _do_mouse_up(self, event):
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        flags = {"left": MOUSEEVENTF_LEFTUP, "right": MOUSEEVENTF_RIGHTUP, "middle": MOUSEEVENTF_MIDDLEUP}.get(button, MOUSEEVENTF_LEFTUP)
        _send_input(_make_mouse_input(x, y, flags))

    def _do_mouse_drag(self, event):
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        flags = {"left": MOUSEEVENTF_MOVE, "right": MOUSEEVENTF_MOVE, "middle": MOUSEEVENTF_MOVE}.get(button, MOUSEEVENTF_MOVE)
        user32.SetCursorPos(int(x), int(y))
        _send_input(_make_mouse_input(x, y, flags))

    def _do_scroll(self, event):
        x, y = event.get("x", 0), event.get("y", 0)
        dy = event.get("dy", 0)
        user32.SetCursorPos(int(x), int(y))
        _send_input(_make_mouse_input(x, y, MOUSEEVENTF_WHEEL, data=dy * 120))

    def _do_key_down(self, event):
        vk = event.get("keycode", 0)
        text = event.get("text", "")
        mods = event.get("modifiers", [])
        if text and len(text) > 1 and vk not in FUNCTION_VK and not mods:
            self._do_type_text({"text": text})
            return
        for mod in mods:
            mod_vk = MODIFIER_VK.get(mod)
            if mod_vk:
                _send_input(_make_key_input(mod_vk))
        time.sleep(0.02)
        _send_input(_make_key_input(vk))

    def _do_key_up(self, event):
        vk = event.get("keycode", 0)
        mods = event.get("modifiers", [])
        _send_input(_make_key_input(vk, KEYEVENTF_KEYUP))
        for mod in reversed(mods):
            mod_vk = MODIFIER_VK.get(mod)
            if mod_vk:
                _send_input(_make_key_input(mod_vk, KEYEVENTF_KEYUP))

    def _do_type_text(self, event):
        text = self._resolve_var(event.get("text", ""))
        if not text:
            return
        if len(text) == 1 and ord(text) < 128:
            vk = ord(text.upper())
            _send_input(_make_key_input(vk))
            time.sleep(0.02)
            _send_input(_make_key_input(vk, KEYEVENTF_KEYUP))
        else:
            _paste_text(text)

    def generate_report(self, script_name=""):
        ok_count = sum(1 for l in self._execution_log if l.get("status") == "ok")
        fail_count = sum(1 for l in self._execution_log if l.get("status") == "fail")
        total = ok_count + fail_count
        rows = ""
        for i, log in enumerate(self._execution_log):
            status_color = "#4caf50" if log.get("status") == "ok" else "#f44336"
            status_text = "OK" if log.get("status") == "ok" else f"FAIL: {log.get('error', '')}"
            rows += f'<tr><td>{log.get("step", "")}</td><td>{log.get("type", "")}</td><td style="color:{status_color}">{status_text}</td></tr>\n'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>执行报告 - {script_name}</title>
<style>body{{font-family:sans-serif;margin:20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f5f5f5}}.summary{{margin:10px 0;font-size:18px}}</style>
</head><body><h1>执行报告: {script_name}</h1>
<div class="summary">总计: {total} | <span style="color:#4caf50">成功: {ok_count}</span> | <span style="color:#f44336">失败: {fail_count}</span></div>
<table><tr><th>步骤</th><th>类型</th><th>状态</th></tr>{rows}</table></body></html>"""
        return html