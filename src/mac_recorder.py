import time
import os
import logging
import threading
import queue
from Quartz import (
    CGEventTapCreate, CGEventTapEnable, CGEventGetIntegerValueField,
    CGEventGetLocation, CGEventGetType, CGEventGetFlags,
    kCGHIDEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
    kCGEventKeyDown, kCGEventKeyUp, kCGEventLeftMouseDown, kCGEventLeftMouseUp,
    kCGEventRightMouseDown, kCGEventRightMouseUp, kCGEventOtherMouseDown,
    kCGEventOtherMouseUp, kCGEventScrollWheel, kCGEventMouseMoved,
    kCGEventLeftMouseDragged, kCGEventRightMouseDragged, kCGEventOtherMouseDragged,
    kCGKeyboardEventKeycode,
    kCGScrollWheelEventDeltaAxis1, kCGScrollWheelEventDeltaAxis2,
    kCGEventFlagMaskCommand, kCGEventFlagMaskShift, kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate,
    CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
    kCFRunLoopDefaultMode, CFRunLoopStop,
    CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)
from Foundation import NSRunLoop, NSDate
import mss
import pytesseract
from PIL import Image

try:
    from accessibility import get_element_at_point, get_element_attrs, get_element_actions
    HAS_ACCESSIBILITY = True
except ImportError:
    HAS_ACCESSIBILITY = False

logger = logging.getLogger("recorder")

OCR_REGION_SIZE = 200
TEMPLATE_SIZE = 80
DRAG_SAMPLE_MIN_DIST = 5

MODIFIER_FLAGS = {
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
}


def _get_modifiers(event):
    flags = CGEventGetFlags(event)
    mods = []
    for name, mask in MODIFIER_FLAGS.items():
        if flags & mask:
            mods.append(name)
    return mods


def _get_unicode_from_event(event):
    try:
        from Quartz import CGEventKeyboardGetUnicodeString
        s = CGEventKeyboardGetUnicodeString(event, 4)
        if s:
            return s
    except Exception:
        pass
    return ""

def _get_unicode_from_event_raw(keycode, flags):
    _KEY_MAP = {
        0: 'a', 1: 's', 2: 'd', 3: 'f', 4: 'h', 5: 'g', 6: 'z', 7: 'x',
        8: 'c', 9: 'v', 11: 'b', 12: 'q', 13: 'w', 14: 'e', 15: 'r',
        16: 'y', 17: 't', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6',
        23: '5', 24: '=', 25: '9', 26: '7', 27: '-', 28: '8', 29: '0',
        30: ']', 31: 'o', 32: 'u', 33: '[', 34: 'i', 35: 'p', 36: '\n',
        37: 'l', 38: ';', 39: "'", 40: 'k', 41: ',', 42: '\\', 43: '/',
        44: 'n', 45: 'm', 46: '.', 47: '\t', 48: ' ', 49: ' ',
        50: '`', 51: '\x1b',
    }
    ch = _KEY_MAP.get(keycode, '')
    if not ch:
        return ''
    if flags & kCGEventFlagMaskShift:
        shift_map = {
            '`': '~', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')', '-': '_',
            '=': '+', '[': '{', ']': '}', '\\': '|', ';': ':', "'": '"',
            ',': '<', '.': '>', '/': '?',
        }
        if ch in shift_map:
            ch = shift_map[ch]
        elif ch.isalpha():
            ch = ch.upper()
    return ch

MODIFIER_FLAGS = {
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
}


def get_window_bounds_at_point(x, y):
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        candidates = []
        for w in window_list:
            bounds_dict = w.get('kCGWindowBounds', {})
            if not bounds_dict:
                continue
            wx = bounds_dict.get('X', 0)
            wy = bounds_dict.get('Y', 0)
            ww = bounds_dict.get('Width', 0)
            wh = bounds_dict.get('Height', 0)
            layer = w.get('kCGWindowLayer', -1)
            pid = w.get('kCGWindowOwnerPID', -1)
            owner = w.get('kCGWindowOwnerName', '')
            title = w.get('kCGWindowName', '')
            if layer != 0 or ww * wh < 100 or pid < 0:
                continue
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                candidates.append((layer, ww * wh, {
                    "pid": pid, "owner": owner, "title": title,
                    "x": wx, "y": wy, "width": ww, "height": wh,
                }))
        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]))
            return candidates[0][2]
    except Exception:
        pass
    return None


def get_window_bounds_by_pid(pid):
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        best = None
        best_area = 0
        for w in window_list:
            if w.get('kCGWindowOwnerPID', -1) != pid:
                continue
            if w.get('kCGWindowLayer', -1) != 0:
                continue
            bounds_dict = w.get('kCGWindowBounds', {})
            if not bounds_dict:
                continue
            wx = bounds_dict.get('X', 0)
            wy = bounds_dict.get('Y', 0)
            ww = bounds_dict.get('Width', 0)
            wh = bounds_dict.get('Height', 0)
            area = ww * wh
            if area < 100:
                continue
            owner = w.get('kCGWindowOwnerName', '')
            title = w.get('kCGWindowName', '')
            if area > best_area:
                best_area = area
                best = {
                    "pid": pid, "owner": owner, "title": title,
                    "x": wx, "y": wy, "width": ww, "height": wh,
                }
        return best
    except Exception:
        pass
    return None


def get_pid_at_point(x, y):
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        candidates = []
        for w in window_list:
            bounds_dict = w.get('kCGWindowBounds', {})
            if not bounds_dict:
                continue
            wx = bounds_dict.get('X', 0)
            wy = bounds_dict.get('Y', 0)
            ww = bounds_dict.get('Width', 0)
            wh = bounds_dict.get('Height', 0)
            layer = w.get('kCGWindowLayer', -1)
            pid = w.get('kCGWindowOwnerPID', -1)
            if layer != 0 or ww * wh < 100:
                continue
            if pid < 0:
                continue
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                candidates.append((layer, ww * wh, pid))
        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]))
            return candidates[0][2]
    except Exception:
        pass
    return None


def get_window_name_at_point(x, y):
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in window_list:
            bounds_dict = w.get('kCGWindowBounds', {})
            if not bounds_dict:
                continue
            wx = bounds_dict.get('X', 0)
            wy = bounds_dict.get('Y', 0)
            ww = bounds_dict.get('Width', 0)
            wh = bounds_dict.get('Height', 0)
            layer = w.get('kCGWindowLayer', -1)
            if layer != 0 or ww * wh < 100:
                continue
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                return w.get('kCGWindowOwnerName', ''), w.get('kCGWindowName', '')
    except Exception:
        pass
    return '', ''


def get_visible_windows():
    try:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        seen = {}
        for w in window_list:
            layer = w.get('kCGWindowLayer', -1)
            if layer != 0:
                continue
            bounds_dict = w.get('kCGWindowBounds', {})
            ww = bounds_dict.get('Width', 0)
            wh = bounds_dict.get('Height', 0)
            if ww * wh < 100:
                continue
            owner = w.get('kCGWindowOwnerName', '')
            pid = w.get('kCGWindowOwnerPID', -1)
            title = w.get('kCGWindowName', '')
            if not owner or pid < 0:
                continue
            if pid not in seen:
                label = f"{owner} (PID:{pid})"
                if title:
                    label += f" - {title}"
                seen[pid] = {"pid": pid, "owner": owner, "title": title, "label": label}
        return list(seen.values())
    except Exception:
        return []


def ocr_at_point(x, y, region_size=OCR_REGION_SIZE, lang="chi_sim+eng"):
    try:
        half = region_size // 2
        region = {
            "left": max(0, int(x) - half),
            "top": max(0, int(y) - half),
            "width": region_size,
            "height": region_size,
        }
        with mss.MSS() as sct:
            screenshot = sct.grab(region)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        results = []
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            tx = data["left"][i] + data["width"][i] // 2
            ty = data["top"][i] + data["height"][i] // 2
            abs_x = region["left"] + tx
            abs_y = region["top"] + ty
            results.append({
                "text": text.strip(),
                "x": abs_x,
                "y": abs_y,
                "offset_x": abs_x - x,
                "offset_y": abs_y - y,
            })
        return results
    except Exception:
        return []


def capture_template(x, y, size=TEMPLATE_SIZE, save_dir=None, index=0):
    try:
        half = size // 2
        region = {
            "left": max(0, int(x) - half),
            "top": max(0, int(y) - half),
            "width": size,
            "height": size,
        }
        with mss.MSS() as sct:
            screenshot = sct.grab(region)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            fname = f"tpl_{index:04d}.png"
            img.save(os.path.join(save_dir, fname))
            return fname
        return None
    except Exception:
        return None


EVENT_MASK = (
    (1 << kCGEventKeyDown) | (1 << kCGEventKeyUp) |
    (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp) |
    (1 << kCGEventRightMouseDown) | (1 << kCGEventRightMouseUp) |
    (1 << kCGEventOtherMouseDown) | (1 << kCGEventOtherMouseUp) |
    (1 << kCGEventScrollWheel) |
    (1 << kCGEventMouseMoved) |
    (1 << kCGEventLeftMouseDragged) | (1 << kCGEventRightMouseDragged) |
    (1 << kCGEventOtherMouseDragged)
)


class MacRecorder:
    def __init__(self, screenshot_interval=2.0, screenshot_dir="screenshots", ocr_anchors=True, visual_templates=True):
        self.events = []
        self.start_time = None
        self.recording = False
        self.screenshot_interval = screenshot_interval
        self.screenshot_dir = screenshot_dir
        self.ocr_anchors = ocr_anchors
        self.visual_templates = visual_templates
        self.last_screenshot_time = 0
        self.screenshot_count = 0
        self._stop_requested = False
        self._tap = None
        self._run_loop = None
        self._ocr_queue = []
        self._last_pid = None
        self._last_pid_time = 0
        self._template_count = 0
        self._template_dir = os.path.join(os.path.dirname(screenshot_dir), "templates")
        self._dragging = False
        self._drag_button = None
        self._drag_last_x = 0
        self._drag_last_y = 0
        self._autosave_path = os.path.join(screenshot_dir, "..", "_recording_autosave.json")
        self._autosave_count = 0
        self._raw_queue = queue.Queue()
        self._my_pid = os.getpid()
        self._target_pid = None
        os.makedirs(screenshot_dir, exist_ok=True)

    def start(self):
        self.events = []
        self.start_time = time.time()
        self.recording = True
        self._stop_requested = False
        self.screenshot_count = 0
        self.last_screenshot_time = 0
        self._last_pid = None
        self._ocr_queue.clear()
        self._template_count = 0
        self._dragging = False
        self._drag_button = None
        self._raw_queue = queue.Queue()
        logger.info("录制初始化, pid=%d, screenshot_dir=%s", self._my_pid, self.screenshot_dir)

        self._tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            EVENT_MASK,
            self._callback,
            None,
        )
        if not self._tap:
            logger.error("CGEventTapCreate返回None, 辅助功能权限可能未授权")
            raise RuntimeError("无法创建事件监听，请在系统设置中授予辅助功能权限")

        CGEventTapEnable(self._tap, True)
        logger.info("CGEventTap已启用")
        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        rl = NSRunLoop.currentRunLoop().getCFRunLoop()
        CFRunLoopAddSource(rl, source, kCFRunLoopDefaultMode)
        self._run_loop = rl
        logger.info("录制开始, NSRunLoop source已添加")

    def stop(self):
        self.recording = False
        self._stop_requested = True
        logger.info("录制停止请求, 队列中剩余raw事件: %d", self._raw_queue.qsize())
        self._process_raw_events()
        if self._tap:
            CGEventTapEnable(self._tap, False)
            logger.info("CGEventTap已禁用")
        if self._run_loop:
            try:
                CFRunLoopStop(self._run_loop)
            except Exception:
                pass
        self._process_ocr_queue()
        logger.info("录制停止, %d 事件, %d OCR锚点, %d 视觉模板", len(self.events), sum(1 for e in self.events if e.get("ocr_anchor")), sum(1 for e in self.events if e.get("template")))
        return self.events

    def should_stop(self):
        return self._stop_requested

    def _elapsed(self):
        return time.time() - self.start_time

    def _autosave(self):
        try:
            import json
            data = {"events": self.events, "autosave": True, "timestamp": time.time()}
            with open(self._autosave_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _get_pid_cached(self, x, y):
        now = time.time()
        if self._last_pid is not None and now - self._last_pid_time < 0.1:
            return self._last_pid
        pid = get_pid_at_point(x, y)
        self._last_pid = pid
        self._last_pid_time = now
        return pid

    def _take_screenshot(self):
        now = time.time()
        if now - self.last_screenshot_time < self.screenshot_interval:
            return
        self.last_screenshot_time = now
        fname = f"screen_{self.screenshot_count:04d}.png"
        fpath = os.path.join(self.screenshot_dir, fname)
        try:
            with mss.MSS() as sct:
                monitor = sct.monitors[1]
                sct.shot(output=fpath)
            crop_bounds = None
            if self._target_pid and self._target_pid != self._my_pid:
                wb = get_window_bounds_by_pid(self._target_pid)
                if wb and wb.get("width", 0) > 50 and wb.get("height", 0) > 50:
                    crop_bounds = wb
            if crop_bounds:
                img = Image.open(fpath)
                cx = max(0, int(crop_bounds["x"]))
                cy = max(0, int(crop_bounds["y"]))
                cw = int(crop_bounds["width"])
                ch = int(crop_bounds["height"])
                if cx + cw <= img.width and cy + ch <= img.height:
                    img = img.crop((cx, cy, cx + cw, cy + ch))
                    img.save(fpath)
                    self.screenshot_count += 1
                    self.events.append({
                        "type": "screenshot",
                        "file": fname,
                        "time": self._elapsed(),
                        "window": crop_bounds,
                    })
                    return
            self.screenshot_count += 1
            self.events.append({
                "type": "screenshot",
                "file": fname,
                "time": self._elapsed(),
            })
        except Exception as e:
            logger.debug("截图异常: %s", e)

    def _process_ocr_queue(self):
        if not self.ocr_anchors or not self._ocr_queue:
            return
        total = len(self._ocr_queue)
        for i, (idx, x, y) in enumerate(self._ocr_queue):
            if idx < len(self.events):
                results = ocr_at_point(x, y)
                if results:
                    closest = min(results, key=lambda r: abs(r["offset_x"]) + abs(r["offset_y"]))
                    self.events[idx]["ocr_anchor"] = {
                        "text": closest["text"],
                        "offset_x": closest["offset_x"],
                        "offset_y": closest["offset_y"],
                    }
            if (i + 1) % 5 == 0 or i == total - 1:
                logger.info("OCR处理: %d/%d", i + 1, total)
        self._ocr_queue.clear()

    def _callback(self, proxy, event_type, event, refcon):
        if not self.recording or self._stop_requested:
            return event
        try:
            loc = CGEventGetLocation(event)
            x = float(loc.x)
            y = float(loc.y)
            flags = int(CGEventGetFlags(event))
            keycode = 0
            if event_type in (kCGEventKeyDown, kCGEventKeyUp):
                keycode = int(CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode))
            dx = 0
            dy = 0
            if event_type == kCGEventScrollWheel:
                dy = int(CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1))
                dx = int(CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis2))
            self._raw_queue.put((event_type, x, y, flags, keycode, dx, dy))
        except Exception:
            pass
        return event

    def _process_raw_events(self):
        processed = 0
        while not self._raw_queue.empty() and processed < 200:
            try:
                event_type, x, y, flags, keycode, dx, dy = self._raw_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            self._handle_event(event_type, x, y, flags, keycode, dx, dy)
        if processed > 0:
            logger.debug("处理raw事件: %d条, 总事件: %d", processed, len(self.events))
            self._autosave_count += processed
            if self._autosave_count >= 10:
                self._autosave()
                self._autosave_count = 0

    def _handle_event(self, event_type, x, y, flags, keycode, dx, dy):
        elapsed = self._elapsed()
        modifiers = []
        if flags & kCGEventFlagMaskCommand:
            modifiers.append("cmd")
        if flags & kCGEventFlagMaskShift:
            modifiers.append("shift")
        if flags & kCGEventFlagMaskControl:
            modifiers.append("ctrl")
        if flags & kCGEventFlagMaskAlternate:
            modifiers.append("alt")

        if event_type in (kCGEventLeftMouseDown, kCGEventRightMouseDown, kCGEventOtherMouseDown):
            pid = self._get_pid_cached(x, y)
            if pid and pid != self._my_pid:
                self._target_pid = pid
            if pid == self._my_pid:
                return

        if event_type == kCGEventLeftMouseDown:
            self._dragging = True
            self._drag_button = "left"
            self._drag_last_x = x
            self._drag_last_y = y
            pid = self._get_pid_cached(x, y)
            self._take_screenshot()
            idx = len(self.events)
            ev = {
                "type": "mouse_down", "x": x, "y": y,
                "button": "left", "time": elapsed, "pid": pid,
            }
            if pid and pid != self._my_pid:
                wb = get_window_bounds_at_point(x, y)
                if wb:
                    ev["window"] = wb
            if modifiers:
                ev["modifiers"] = modifiers
            if self.visual_templates:
                tpl_file = capture_template(x, y, save_dir=self._template_dir, index=self._template_count)
                if tpl_file:
                    ev["template"] = tpl_file
                    self._template_count += 1
            if HAS_ACCESSIBILITY and pid:
                try:
                    elem = get_element_at_point(pid, x, y)
                    if elem:
                        attrs = get_element_attrs(elem)
                        if attrs:
                            ev["ax_element"] = attrs
                            actions = get_element_actions(elem)
                            if actions:
                                ev["ax_actions"] = actions
                except Exception:
                    pass
            self.events.append(ev)
            if self.ocr_anchors:
                self._ocr_queue.append((idx, x, y))
        elif event_type == kCGEventLeftMouseUp:
            self._dragging = False
            pid = self._last_pid
            ev = {
                "type": "mouse_up", "x": x, "y": y,
                "button": "left", "time": elapsed, "pid": pid,
            }
            if modifiers:
                ev["modifiers"] = modifiers
            self.events.append(ev)
        elif event_type == kCGEventRightMouseDown:
            self._dragging = True
            self._drag_button = "right"
            self._drag_last_x = x
            self._drag_last_y = y
            pid = self._get_pid_cached(x, y)
            self._take_screenshot()
            idx = len(self.events)
            ev = {
                "type": "mouse_down", "x": x, "y": y,
                "button": "right", "time": elapsed, "pid": pid,
            }
            if modifiers:
                ev["modifiers"] = modifiers
            if self.visual_templates:
                tpl_file = capture_template(x, y, save_dir=self._template_dir, index=self._template_count)
                if tpl_file:
                    ev["template"] = tpl_file
                    self._template_count += 1
            if HAS_ACCESSIBILITY and pid:
                try:
                    elem = get_element_at_point(pid, x, y)
                    if elem:
                        attrs = get_element_attrs(elem)
                        if attrs:
                            ev["ax_element"] = attrs
                except Exception:
                    pass
            self.events.append(ev)
            if self.ocr_anchors:
                self._ocr_queue.append((idx, x, y))
        elif event_type == kCGEventRightMouseUp:
            self._dragging = False
            pid = self._last_pid
            ev = {
                "type": "mouse_up", "x": x, "y": y,
                "button": "right", "time": elapsed, "pid": pid,
            }
            if modifiers:
                ev["modifiers"] = modifiers
            self.events.append(ev)
        elif event_type in (kCGEventLeftMouseDragged, kCGEventRightMouseDragged, kCGEventOtherMouseDragged):
            ddx = x - self._drag_last_x
            ddy = y - self._drag_last_y
            if ddx * ddx + ddy * ddy >= DRAG_SAMPLE_MIN_DIST * DRAG_SAMPLE_MIN_DIST:
                pid = self._last_pid
                self.events.append({
                    "type": "mouse_drag", "x": x, "y": y,
                    "button": self._drag_button or "left",
                    "time": elapsed, "pid": pid,
                })
                self._drag_last_x = x
                self._drag_last_y = y
        elif event_type == kCGEventScrollWheel:
            pid = self._last_pid
            self.events.append({
                "type": "scroll", "x": x, "y": y,
                "dx": dx, "dy": dy, "time": elapsed, "pid": pid,
            })
        elif event_type == kCGEventKeyDown:
            pid = self._last_pid
            if keycode == 111:
                self._stop_requested = True
                return
            self._take_screenshot()
            unicode_char = _get_unicode_from_event_raw(keycode, flags)
            ev = {
                "type": "key_down", "keycode": keycode,
                "time": elapsed, "pid": pid,
            }
            if modifiers:
                ev["modifiers"] = modifiers
            if unicode_char:
                ev["text"] = unicode_char
            self.events.append(ev)
        elif event_type == kCGEventKeyUp:
            pid = self._last_pid
            keycode_val = keycode
            ev = {
                "type": "key_up", "keycode": keycode_val,
                "time": elapsed, "pid": pid,
            }
            if modifiers:
                ev["modifiers"] = modifiers
            self.events.append(ev)
