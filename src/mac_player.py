import time
import logging
import os
import subprocess
import threading
from Quartz import (
    CGEventCreateMouseEvent, CGEventCreateKeyboardEvent,
    CGEventCreateScrollWheelEvent, CGEventPost, CGEventPostToPid,
    CGEventSetFlags, CGEventSetSource,
    CGPoint, kCGHIDEventTap,
    kCGEventLeftMouseDown, kCGEventLeftMouseUp,
    kCGEventRightMouseDown, kCGEventRightMouseUp,
    kCGEventOtherMouseDown, kCGEventOtherMouseUp,
    kCGEventLeftMouseDragged, kCGEventRightMouseDragged, kCGEventOtherMouseDragged,
    kCGEventKeyDown, kCGEventKeyUp,
    kCGMouseButtonLeft, kCGMouseButtonRight, kCGMouseButtonCenter,
    kCGScrollEventUnitPixel,
    kCGEventFlagMaskCommand, kCGEventFlagMaskShift, kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate,
)
import mss
import pytesseract
from PIL import Image
import cv2
import numpy as np

try:
    from accessibility import find_element_by_attrs, perform_action, set_value
    HAS_ACCESSIBILITY = True
except ImportError:
    HAS_ACCESSIBILITY = False

logger = logging.getLogger("player")

OCR_REGION_SIZE = 200
TEMPLATE_SIZE = 80
TEMPLATE_MATCH_THRESHOLD = 0.55

MODIFIER_KEYCODES = {
    "cmd": 0x37,
    "shift": 0x38,
    "ctrl": 0x3B,
    "alt": 0x3A,
}

MODIFIER_FLAGS = {
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
}

FUNCTION_KEYCODES = set(range(122, 127)) | {0x24, 0x30, 0x31, 0x33, 0x35, 0x7A, 0x78, 0x63, 0x76, 0x61, 0x60}


def _paste_text(text):
    try:
        old = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2).stdout
    except Exception:
        old = ""
    try:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=2)
    except Exception:
        return False
    time.sleep(0.02)
    cmd_down = CGEventCreateKeyboardEvent(None, 0x37, True)
    v_down = CGEventCreateKeyboardEvent(None, 0x09, True)
    v_up = CGEventCreateKeyboardEvent(None, 0x09, False)
    cmd_up = CGEventCreateKeyboardEvent(None, 0x37, False)
    CGEventPost(kCGHIDEventTap, cmd_down)
    CGEventPost(kCGHIDEventTap, v_down)
    CGEventPost(kCGHIDEventTap, v_up)
    CGEventPost(kCGHIDEventTap, cmd_up)
    time.sleep(0.05)
    try:
        subprocess.run(["pbcopy"], input=old, text=True, timeout=2)
    except Exception:
        pass
    return True


def _activate_app(pid):
    try:
        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        wl = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in wl:
            if w.get('kCGWindowOwnerPID', -1) == pid:
                app_name = w.get('kCGWindowOwnerName', '')
                if app_name:
                    subprocess.run(["osascript", "-e", f'tell application "{app_name}" to activate'],
                                   capture_output=True, timeout=3)
                    time.sleep(0.3)
                    return True
    except Exception:
        pass
    return False


def ocr_find_text(target_text, lang="chi_sim+eng", region=None):
    try:
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


class MacPlayer:
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
            start_time = events[0]["time"] if events else 0
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
                            self._variables[name] = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2).stdout
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
                    result = None
                    try:
                        import ai_recognizer as ai
                        region = event.get("region")
                        if region and region != "自动截图":
                            result = ai.recognize_captcha(region=None, prompt=prompt)
                        else:
                            tmp_path = os.path.join(os.path.expanduser("~"), "GhostAction", "tmp_ai_capture.png")
                            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
                            with mss.MSS() as sct:
                                screenshot = sct.grab(sct.monitors[1])
                                from PIL import Image as PILImage
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
                    self._execution_log.append({"step": self._event_index, "type": etype, "status": "fail", "error": str(e)})
                    if self.on_error == "abort":
                        self._stop = True
                    elif self.on_error == "skip":
                        logger.warning("步骤 %d 失败, 跳过", self._event_index)
                    else:
                        logger.warning("步骤 %d 失败, 继续执行", self._event_index)

    def _get_target_window_bounds(self, event):
        pid = event.get("pid") or self.target_pid
        if not pid:
            return None
        try:
            from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            wl = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            for w in wl:
                if w.get('kCGWindowOwnerPID', -1) == pid:
                    bounds = w.get('kCGWindowBounds', {})
                    if bounds:
                        return {"x": bounds.get('X', 0), "y": bounds.get('Y', 0),
                                "width": bounds.get('Width', 0), "height": bounds.get('Height', 0)}
        except Exception:
            pass
        return None

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
                        logger.info("视觉匹配: %s 原始=(%.0f,%.0f) 新=(%.0f,%.0f) 置信度=%.2f", tpl_file, event["x"], event["y"], new_x, new_y, confidence)
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
                    if 0 <= new_x <= 1920 and 0 <= new_y <= 1080:
                        logger.info("OCR定位: '%s' 原始=(%.0f,%.0f) 新=(%.0f,%.0f)", target_text, event["x"], event["y"], new_x, new_y)
                        return new_x, new_y
                    logger.warning("OCR定位坐标异常: '%s' 新=(%.0f,%.0f), 回退原始坐标", target_text, new_x, new_y)
            else:
                logger.info("OCR锚点太短('%s'), 跳过OCR定位", target_text)
            logger.warning("OCR定位失败: '%s', 回退原始坐标", target_text)

        return event["x"], event["y"]

    def _post_event(self, event_obj, pid=None):

        CGEventPost(kCGHIDEventTap, event_obj)

    def _press_modifiers(self, modifiers):
        if not modifiers:
            return
        for mod in modifiers:
            kc = MODIFIER_KEYCODES.get(mod)
            if kc:
                CGEventPost(kCGHIDEventTap, CGEventCreateKeyboardEvent(None, kc, True))
        time.sleep(0.02)

    def _release_modifiers(self, modifiers):
        if not modifiers:
            return
        for mod in reversed(modifiers):
            kc = MODIFIER_KEYCODES.get(mod)
            if kc:
                CGEventPost(kCGHIDEventTap, CGEventCreateKeyboardEvent(None, kc, False))
        time.sleep(0.02)

    def _execute(self, event):
        etype = event["type"]
        pid = event.get("pid")
        if etype == "mouse_down":
            self._do_mouse_down(event, pid)
        elif etype == "mouse_up":
            self._do_mouse_up(event, pid)
        elif etype == "mouse_drag":
            self._do_mouse_drag(event, pid)
        elif etype == "scroll":
            self._do_scroll(event, pid)
        elif etype == "key_down":
            self._do_key_down(event, pid)
        elif etype == "key_up":
            self._do_key_up(event, pid)
        elif etype == "type_text":
            self._do_type_text(event, pid)
        elif etype == "wait_for":
            self._do_wait_for(event)
        elif etype == "assert_that":
            self._do_assert(event)
        elif etype == "activate":
            self._do_activate(event)
        elif etype == "set_variable":
            pass
        elif etype == "call_script":
            pass
        elif etype == "comment":
            pass
        elif etype == "ai_recognize":
            pass
        elif etype == "wait_manual":
            pass

    def _do_mouse_down(self, event, pid=None):
        if pid == os.getpid():
            logger.info("跳过自身窗口点击: PID=%d", pid)
            return
        ax_elem = event.get("ax_element")
        target_pid = pid or self.target_pid
        if HAS_ACCESSIBILITY and ax_elem:
            if target_pid:
                try:
                    elem = find_element_by_attrs(target_pid, ax_elem, timeout=2)
                    if elem:
                        actions = event.get("ax_actions", [])
                        if "AXPress" in actions:
                            _activate_app(target_pid)
                            time.sleep(0.2)
                            if perform_action(elem, "AXPress"):
                                logger.info("Accessibility点击: %s", ax_elem.get("AXRole", ""))
                                return
                except Exception:
                    pass
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        modifiers = event.get("modifiers", [])
        if pid:
            _activate_app(pid)
            time.sleep(0.1)
        self._press_modifiers(modifiers)
        if button == "left":
            etype = kCGEventLeftMouseDown
            btn = kCGMouseButtonLeft
        elif button == "right":
            etype = kCGEventRightMouseDown
            btn = kCGMouseButtonRight
        else:
            etype = kCGEventOtherMouseDown
            btn = kCGMouseButtonCenter
        event_obj = CGEventCreateMouseEvent(None, etype, CGPoint(x, y), btn)
        self._post_event(event_obj, pid)

    def _do_mouse_up(self, event, pid=None):
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        modifiers = event.get("modifiers", [])
        if button == "left":
            etype = kCGEventLeftMouseUp
            btn = kCGMouseButtonLeft
        elif button == "right":
            etype = kCGEventRightMouseUp
            btn = kCGMouseButtonRight
        else:
            etype = kCGEventOtherMouseUp
            btn = kCGMouseButtonCenter
        event_obj = CGEventCreateMouseEvent(None, etype, CGPoint(x, y), btn)
        self._post_event(event_obj, pid)
        self._release_modifiers(modifiers)

    def _do_mouse_drag(self, event, pid=None):
        x, y = self._resolve_coords(event)
        button = event.get("button", "left")
        if button == "left":
            etype = kCGEventLeftMouseDragged
            btn = kCGMouseButtonLeft
        elif button == "right":
            etype = kCGEventRightMouseDragged
            btn = kCGMouseButtonRight
        else:
            etype = kCGEventOtherMouseDragged
            btn = kCGMouseButtonCenter
        event_obj = CGEventCreateMouseEvent(None, etype, CGPoint(x, y), btn)
        self._post_event(event_obj, pid)

    def _do_scroll(self, event, pid=None):
        dx, dy = event.get("dx", 0), event.get("dy", 0)
        event_obj = CGEventCreateScrollWheelEvent(
            None, kCGScrollEventUnitPixel, 2, dy, dx
        )
        self._post_event(event_obj, pid)

    def _do_key_down(self, event, pid=None):
        keycode = event["keycode"]
        text = event.get("text", "")
        modifiers = event.get("modifiers", [])
        if text and len(text) > 1 and keycode not in FUNCTION_KEYCODES and not modifiers:
            self._do_type_text({"text": text, "pid": pid}, pid)
            return
        self._press_modifiers(modifiers)
        event_obj = CGEventCreateKeyboardEvent(None, keycode, True)
        self._post_event(event_obj, pid)

    def _do_key_up(self, event, pid=None):
        keycode = event["keycode"]
        modifiers = event.get("modifiers", [])
        event_obj = CGEventCreateKeyboardEvent(None, keycode, False)
        self._post_event(event_obj, pid)
        self._release_modifiers(modifiers)

    def _do_type_text(self, event, pid=None):
        text = self._resolve_var(event.get("text", ""))
        if not text:
            return
        if len(text) == 1 and ord(text) < 128:
            from Quartz import CGEventSetUnicodeString
            event_obj = CGEventCreateKeyboardEvent(None, 0, True)
            CGEventSetUnicodeString(event_obj, text)
            self._post_event(event_obj, pid)
            event_obj2 = CGEventCreateKeyboardEvent(None, 0, False)
            CGEventSetUnicodeString(event_obj2, text)
            self._post_event(event_obj2, pid)
        else:
            _paste_text(text)

    def _do_wait_for(self, event):
        strategy = event.get("strategy", "template")
        timeout = event.get("timeout", 10)
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
                with mss.MSS() as sct:
                    px = sct.grab({"left": x, "top": y, "width": 1, "height": 1})
                    r, g, b = px.pixel(0, 0)[:3]
                    return abs(r - expected[0]) <= tolerance and abs(g - expected[1]) <= tolerance and abs(b - expected[2]) <= tolerance
            except Exception:
                return False
        elif strategy == "pixel_change":
            return True
        elif strategy == "element":
            if HAS_ACCESSIBILITY:
                pid = event.get("pid") or self.target_pid
                attrs = event.get("ax_element", {})
                if pid and attrs:
                    elem = find_element_by_attrs(pid, attrs, timeout=0.5)
                    return elem is not None
            return False
        return False

    def click_at(self, x, y, button="left", pid=None):
        self._do_mouse_down({"x": x, "y": y, "button": button}, pid)
        time.sleep(0.05)
        self._do_mouse_up({"x": x, "y": y, "button": button}, pid)

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
