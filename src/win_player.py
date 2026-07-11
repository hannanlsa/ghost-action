import time
import logging
import os
import subprocess
import threading
import ctypes
import ctypes.wintypes
from ctypes import windll, byref, sizeof, Structure, POINTER, c_uint64

if not hasattr(ctypes.wintypes, 'ULONG_PTR'):
    ctypes.wintypes.ULONG_PTR = c_uint64

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
                 retry_count=3, retry_interval=1.0, global_timeout=300, on_error="retry", use_ai_fallback=True,
                 browser_engine=None, browser_profile=None):
        self.speed = speed
        self.target_pid = target_pid
        self.smart_replay = smart_replay
        self.visual_match = visual_match
        self.scripts_dir = scripts_dir
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.global_timeout = global_timeout
        self.on_error = on_error
        self.use_ai_fallback = use_ai_fallback
        self._browser_engine = browser_engine
        self._browser_profile = browser_profile
        self._stop = False
        self._paused = threading.Event()
        self._paused.set()
        self._event_index = 0
        self._total_events = 0
        self._start_wall_time = None
        self._execution_log = []
        self._variables = {}
        try:
            from adaptive_engine import AdaptiveEngine
            self._adaptive = AdaptiveEngine(scripts_dir=scripts_dir, use_ai_fallback=use_ai_fallback)
        except ImportError:
            self._adaptive = None

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

        if self.smart_replay and self._adaptive and self.target_pid:
            cur_bounds = self._get_target_window_bounds({"pid": self.target_pid})
            if cur_bounds:
                self._adaptive.record_window_bounds(self.target_pid, cur_bounds)

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

                if etype == "if":
                    cond_met = self._check_condition(event)
                    if not cond_met:
                        depth = 1
                        while i + 1 < len(events) and depth > 0:
                            i += 1
                            t = events[i].get("type", "")
                            if t == "if":
                                depth += 1
                            elif t == "endif":
                                depth -= 1
                        i += 1
                        continue
                    i += 1
                    continue

                if etype == "endif":
                    i += 1
                    continue

                if etype == "for":
                    count = event.get("count", 1)
                    var_name = event.get("variable", "_i")
                    end_idx = self._find_end(events, i, "for", "endfor")
                    if end_idx is None:
                        i += 1
                        continue
                    body = events[i + 1:end_idx]
                    for iteration in range(count):
                        if self._stop:
                            break
                        self._variables[var_name] = iteration
                        self.play(body, variables=self._variables, _recursive=True)
                    i = end_idx + 1
                    continue

                if etype == "endfor":
                    i += 1
                    continue

                if etype == "while":
                    end_idx = self._find_end(events, i, "while", "endwhile")
                    if end_idx is None:
                        i += 1
                        continue
                    body = events[i + 1:end_idx]
                    max_iter = event.get("max_iterations", 1000)
                    iteration = 0
                    while iteration < max_iter:
                        if self._stop:
                            break
                        if not self._check_condition(event):
                            break
                        self.play(body, variables=self._variables, _recursive=True)
                        iteration += 1
                    i = end_idx + 1
                    continue

                if etype == "endwhile":
                    i += 1
                    continue

                if etype == "set_variable":
                    name = event.get("name", "")
                    value_from = event.get("value_from", "literal")
                    if value_from == "literal":
                        self._variables[name] = self._resolve_var(event.get("value", ""))
                    elif value_from == "ocr":
                        text = event.get("text", "")
                        results = ocr_find_text(text)
                        self._variables[name] = results[0][2] if results else ""
                    elif value_from == "clipboard":
                        try:
                            import pyperclip
                            self._variables[name] = pyperclip.paste()
                        except Exception:
                            self._variables[name] = ""
                    self._execution_log.append({"step": i, "type": "set_variable", "status": "ok", "variable": name})
                    i += 1
                    continue

                if etype == "call_script":
                    script_name = event.get("script_name", "")
                    if script_name and self.scripts_dir:
                        from script_manager import ScriptManager
                        sm = ScriptManager(scripts_dir=os.path.join(self.scripts_dir, "scripts"))
                        data = sm.load(script_name)
                        if data:
                            sub_events = [e for e in data.get("events", []) if not e.get("disabled")]
                            params = event.get("params", {})
                            merged_vars = dict(self._variables)
                            merged_vars.update(params)
                            self.play(sub_events, variables=merged_vars, _recursive=True)
                    i += 1
                    continue

                if etype == "comment":
                    i += 1
                    continue

                if etype == "ai_recognize":
                    var_name = event.get("variable", "")
                    prompt = event.get("prompt", "请识别图中的验证码，只输出验证码内容")
                    target = event.get("target", "验证码")
                    mode = event.get("mode", "vision")
                    result = None
                    try:
                        import ai_recognizer as ai
                        if mode == "text":
                            resolved_prompt = self._resolve_var(prompt)
                            result = ai.recognize_text(resolved_prompt)
                        else:
                            region = event.get("region")
                            if region and region != "自动截图":
                                result = ai.recognize_captcha(region=None, prompt=prompt)
                            else:
                                tmp_path = os.path.join(os.path.expanduser("~"), "GhostAction", "tmp_ai_capture.png")
                                os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
                                import mss
                                from PIL import Image as PILImage
                                with mss.MSS() as sct:
                                    screenshot = sct.grab(sct.monitors[1])
                                    img = PILImage.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                                    img.save(tmp_path)
                                result = ai.recognize_captcha(image_path=tmp_path, prompt=prompt)
                                try:
                                    os.remove(tmp_path)
                                except Exception:
                                    pass
                    except ImportError:
                        logger.warning("ai_recognizer模块不可用")
                    except Exception as e:
                        logger.error("AI识别异常: %s", e)
                    if result:
                        self._variables[var_name] = result
                        logger.info("AI识别成功: %s = %s", var_name, result)
                        self._execution_log.append({"step": i, "type": "ai_recognize", "status": "ok", "variable": var_name, "result": result})
                    else:
                        logger.warning("AI识别失败: %s", target)
                        self._execution_log.append({"step": i, "type": "ai_recognize", "status": "fail", "variable": var_name})
                        if not event.get("fallback_manual", True):
                            self._variables[var_name] = ""
                    i += 1
                    continue

                if etype == "wait_manual":
                    desc = event.get("description", "请手动操作后继续")
                    var_name = event.get("variable", "")
                    logger.info("等待人工: %s", desc)
                    self._execution_log.append({"step": i, "type": "wait_manual", "status": "waiting", "description": desc})
                    manual_file = os.path.join(os.path.expanduser("~"), "GhostAction", "manual_signal.txt")
                    try:
                        os.makedirs(os.path.dirname(manual_file), exist_ok=True)
                        if os.path.exists(manual_file):
                            os.remove(manual_file)
                    except Exception:
                        pass
                    wait_timeout = 120
                    start = time.time()
                    while time.time() - start < wait_timeout:
                        if self._stop:
                            break
                        self._paused.wait()
                        if os.path.exists(manual_file):
                            try:
                                with open(manual_file, "r", encoding="utf-8") as f:
                                    content = f.read().strip()
                                if content:
                                    if var_name:
                                        self._variables[var_name] = content
                                        logger.info("人工输入: %s = %s", var_name, content)
                                    os.remove(manual_file)
                                    break
                            except Exception:
                                pass
                        time.sleep(0.5)
                    self._execution_log.append({"step": i, "type": "wait_manual", "status": "ok"})
                    i += 1
                    continue

                step_delay = {
                    "mouse_down": 0.3, "mouse_up": 0.05, "mouse_drag": 0.3,
                    "key_down": 0.1, "key_up": 0.05, "scroll": 0.3,
                    "type_text": 0.1, "screenshot": 0.05,
                    "wait_for": 0.1, "assert_that": 0.1,
                    "activate": 0.5, "set_variable": 0.05,
                    "call_script": 0.1,
                }.get(etype, 0.2)
                time.sleep(step_delay / self.speed)
                self._execute_with_retry(event)
                i += 1
        except Exception as e:
            logger.error("回放异常: %s", e)

    def _find_end(self, events, start, open_type, close_type):
        depth = 1
        i = start + 1
        while i < len(events):
            t = events[i].get("type", "")
            if t == open_type:
                depth += 1
            elif t == close_type:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

    def _execute_with_retry(self, event):
        etype = event.get("type")
        max_attempts = self.retry_count + 1 if etype in ("mouse_down", "mouse_up") else 1
        for attempt in range(max_attempts):
            try:
                self._execute(event)
                self._execution_log.append({"step": self._event_index, "type": etype, "status": "ok", "attempt": attempt})
                return
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning("步骤 %d 执行失败(尝试 %d/%d): %s, %0.1fs后重试",
                                   self._event_index, attempt + 1, max_attempts, e, self.retry_interval)
                    time.sleep(self.retry_interval)
                else:
                    if self.smart_replay and self._adaptive and etype in ("mouse_down", "type_text"):
                        alt_paths = self._adaptive.find_alternative_path(event, "coordinate")
                        for alt_type, alt_data in alt_paths:
                            logger.info("尝试替代路径: %s", alt_type)
                            if self._adaptive.execute_alternative(
                                    alt_type, alt_data,
                                    browser_engine=self._browser_engine,
                                    browser_profile=self._browser_profile,
                                    pid=event.get("pid") or self.target_pid):
                                self._execution_log.append({"step": self._event_index, "type": etype, "status": "ok", "attempt": attempt, "alternative": alt_type})
                                return
                    self._execution_log.append({"step": self._event_index, "type": etype, "status": "fail", "error": str(e)})
                    if self.on_error == "abort":
                        self._stop = True
                    elif self.on_error == "skip":
                        logger.warning("步骤 %d 失败, 跳过", self._event_index)
                    else:
                        logger.warning("步骤 %d 失败, 继续执行", self._event_index)

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
        elif etype == "wait_for":
            self._do_wait_for(event)
        elif etype == "assert_that":
            self._do_assert(event)
        elif etype == "activate":
            self._do_activate(event)
        elif etype in ("set_variable", "call_script", "comment", "ai_recognize", "wait_manual"):
            pass

    def _resolve_coords(self, event):
        if "x" not in event:
            return 0, 0
        win_bounds = self._get_target_window_bounds(event)

        if self.smart_replay and self._adaptive and win_bounds:
            recorded_bounds = event.get("window_bounds") or event.get("window")
            if recorded_bounds:
                adapted_x, adapted_y = self._adaptive.adapt_coordinates(
                    event["x"], event["y"], recorded_bounds, win_bounds)
                if adapted_x != event["x"] or adapted_y != event["y"]:
                    logger.info("坐标适配: 原始=(%.0f,%.0f) 适配=(%.0f,%.0f)", event["x"], event["y"], adapted_x, adapted_y)
                    event = dict(event)
                    event["x"] = adapted_x
                    event["y"] = adapted_y

        if self.visual_match:
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
                        logger.warning("视觉匹配失败: %s, 尝试OCR", tpl_file)
                        break

        anchor = event.get("ocr_anchor")
        if anchor:
            target_text = anchor["text"]
            offset_x = anchor["offset_x"]
            offset_y = anchor["offset_y"]
            if len(target_text) >= 2:
                region = {
                    "left": max(0, int(event["x"]) - OCR_REGION_SIZE),
                    "top": max(0, int(event["y"]) - OCR_REGION_SIZE),
                    "width": OCR_REGION_SIZE * 2,
                    "height": OCR_REGION_SIZE * 2,
                }
                results = ocr_find_text(target_text, region=region)
                if not results:
                    logger.info("OCR局部搜索失败: '%s', 尝试全屏搜索", target_text)
                    results = ocr_find_text(target_text)
                if results:
                    best_x, best_y, _ = results[0]
                    new_x = best_x - offset_x
                    new_y = best_y - offset_y
                    if 0 <= new_x <= 3000 and 0 <= new_y <= 2000:
                        logger.info("OCR定位: '%s' 新=(%.0f,%.0f)", target_text, new_x, new_y)
                        return new_x, new_y
                    logger.warning("OCR定位坐标异常: '%s' 新=(%.0f,%.0f), 回退原始坐标", target_text, new_x, new_y)
            else:
                logger.info("OCR锚点太短('%s'), 跳过OCR定位", target_text)
            logger.warning("OCR定位失败: '%s', 回退原始坐标", target_text)

        if self.use_ai_fallback:
            ai_coords = self._ai_locate(event)
            if ai_coords:
                return ai_coords

        return event["x"], event["y"]

    def _ai_locate(self, event):
        try:
            import ai_recognizer
        except ImportError:
            return None

        target_desc = ""
        ax = event.get("ax_element", {})
        if ax.get("AXTitle"):
            target_desc = ax["AXTitle"]
        elif ax.get("AXRoleDescription"):
            target_desc = ax["AXRoleDescription"]
        anchor = event.get("ocr_anchor", {})
        if not target_desc and anchor.get("text"):
            target_desc = anchor["text"]
        if not target_desc:
            return None

        tmp_path = os.path.join(os.path.expanduser("~"), "GhostAction", "tmp_ai_locate.png")
        try:
            import mss
            from PIL import Image
            with mss.MSS() as sct:
                screenshot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img.save(tmp_path)
        except Exception:
            return None

        if not os.path.exists(tmp_path):
            return None

        try:
            result = ai_recognizer.locate_on_screen_with_fallback(tmp_path, target_desc)
            if result:
                x, y = result
                logger.info("AI兜底定位: 「%s」→ (%d, %d)", target_desc, x, y)
                return x, y
        except Exception as e:
            logger.warning("AI兜底定位异常: %s", e)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        return None

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

    def _do_wait_for(self, event):
        strategy = event.get("strategy", "template")
        timeout = event.get("timeout", 10)
        if self.smart_replay and self._adaptive:
            tpl_file = event.get("template")
            tpl_path = None
            if tpl_file and self.scripts_dir:
                for subdir in ["scripts/templates", "templates"]:
                    p = os.path.join(self.scripts_dir, subdir, tpl_file)
                    if os.path.exists(p):
                        tpl_path = p
                        break
            ocr_text = event.get("text") if strategy == "ocr" else None
            result = self._adaptive.smart_wait(
                strategy=strategy, timeout=timeout,
                template_path=tpl_path, ocr_text=ocr_text)
            if result:
                logger.info("智能等待满足: %s", strategy)
            else:
                logger.warning("智能等待超时: %s (%ds)", strategy, timeout)
            return
        interval = event.get("interval", 0.5)
        start = time.time()
        while time.time() - start < timeout:
            if self._stop:
                return
            if self._check_condition(event):
                logger.info("等待条件满足: %s (%.1fs)", strategy, time.time() - start)
                return
            time.sleep(interval)
        logger.warning("等待超时: %s (%ds)", strategy, timeout)

    def _do_assert(self, event):
        timeout = event.get("timeout", 5)
        start = time.time()
        while time.time() - start < timeout:
            if self._check_condition(event):
                logger.info("断言通过: %s", event.get("description", ""))
                return
            time.sleep(0.3)
        msg = event.get("description", "断言失败")
        logger.error("断言失败: %s", msg)
        if event.get("on_fail", "warn") == "abort":
            self._stop = True

    def _do_activate(self, event):
        pid = event.get("pid") or self.target_pid
        if pid:
            _activate_app(pid)

    def _check_condition(self, event):
        strategy = event.get("strategy", "template")
        if strategy == "template":
            tpl_file = event.get("template")
            if tpl_file and self.scripts_dir:
                tpl_path = None
                for subdir in ["scripts/templates", "templates"]:
                    p = os.path.join(self.scripts_dir, subdir, tpl_file)
                    if os.path.exists(p):
                        tpl_path = p
                        break
                if tpl_path:
                    result = template_match(tpl_path, threshold=event.get("threshold", TEMPLATE_MATCH_THRESHOLD))
                    return result is not None
        elif strategy == "ocr":
            target_text = event.get("text", "")
            region = event.get("region")
            results = ocr_find_text(target_text, region=region)
            return len(results) > 0
        elif strategy == "color":
            x, y = event.get("x", 0), event.get("y", 0)
            expected = event.get("color", [])
            tolerance = event.get("tolerance", 20)
            if not expected or len(expected) != 3:
                return False
            try:
                import mss
                with mss.MSS() as sct:
                    px = sct.grab({"left": x, "top": y, "width": 1, "height": 1})
                    r, g, b = px.pixel(0, 0)[:3]
                    return abs(r - expected[0]) <= tolerance and abs(g - expected[1]) <= tolerance and abs(b - expected[2]) <= tolerance
            except Exception:
                return False
        elif strategy == "pixel_change":
            if self._adaptive:
                return self._adaptive._check_pixel_change()
            return True
        return False

    def click_at(self, x, y, button="left"):
        self._do_mouse_down({"x": x, "y": y, "button": button})
        time.sleep(0.05)
        self._do_mouse_up({"x": x, "y": y, "button": button})

    def find_text_on_screen(self, target_text, lang="chi_sim+eng"):
        results = ocr_find_text(target_text, lang=lang)
        return results[0][:2] if results else None

    def click_text(self, target_text, lang="chi_sim+eng"):
        pos = self.find_text_on_screen(target_text, lang)
        if pos:
            self.click_at(pos[0], pos[1])
            return True
        return False

    def generate_report(self, script_name=""):
        ok_count = sum(1 for l in self._execution_log if l.get("status") == "ok")
        fail_count = sum(1 for l in self._execution_log if l.get("status") == "fail")
        total = ok_count + fail_count
        rows = ""
        for i, log in enumerate(self._execution_log):
            status_color = "#4caf50" if log.get("status") == "ok" else "#f44336"
            status_text = "OK" if log.get("status") == "ok" else f"FAIL: {log.get('error', '')}"
            rows += f'<tr><td>{log.get("step", "")}</td><td>{log.get("type", "")}</td><td style="color:{status_color}">{status_text}</td><td>{log.get("attempt", 0)}</td></tr>\n'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>执行报告 - {script_name}</title>
<style>body{{font-family:sans-serif;margin:20px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f5f5f5}}.summary{{margin:10px 0;font-size:18px}}</style>
</head><body><h1>执行报告: {script_name}</h1>
<div class="summary">总计: {total} | <span style="color:#4caf50">成功: {ok_count}</span> | <span style="color:#f44336">失败: {fail_count}</span></div>
<table><tr><th>步骤</th><th>类型</th><th>状态</th><th>尝试</th></tr>{rows}</table></body></html>"""
        return html
