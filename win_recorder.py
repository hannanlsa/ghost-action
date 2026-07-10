import time
import os
import logging
import threading
import queue
import ctypes
import ctypes.wintypes
from ctypes import windll, Structure, POINTER, byref, sizeof, c_long, c_ulong, c_uint64

if not hasattr(ctypes.wintypes, 'ULONG_PTR'):
    ctypes.wintypes.ULONG_PTR = c_uint64

logger = logging.getLogger("win_recorder")

OCR_REGION_SIZE = 200
TEMPLATE_SIZE = 80

user32 = windll.user32
kernel32 = windll.kernel32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002

WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEMOVE = 0x0200

VK_MAP = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Return", 0x10: "Shift",
    0x11: "Ctrl", 0x12: "Alt", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up",
    0x27: "Right", 0x28: "Down", 0x2C: "PrintScreen", 0x2D: "Insert",
    0x2E: "Delete", 0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
    0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
    0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
}


class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("x", ctypes.wintypes.LONG),
        ("y", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR),
    ]


class KBDLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR),
    ]


HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)


def get_window_at_point(x, y):
    hwnd = user32.WindowFromPoint(ctypes.wintypes.POINT(x, y))
    if not hwnd:
        return None, "", "", {}
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, byref(pid))
    length = 256
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value
    class_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buf, 256)
    cls = class_buf.value
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, byref(rect))
    bounds = {"x": rect.left, "y": rect.top, "width": rect.right - rect.left, "height": rect.bottom - rect.top}
    return pid.value, title, cls, bounds


def get_visible_windows():
    windows = []
    seen = set()

    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, byref(pid))
        if pid.value in seen:
            return True
        seen.add(pid.value)
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w * h < 100:
            return True
        windows.append({
            "pid": pid.value,
            "owner": title,
            "title": title,
            "label": f"{title} (PID:{pid.value})",
        })
        return True

    CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(CB(enum_cb), 0)
    return windows


def ocr_at_point(x, y, region_size=OCR_REGION_SIZE, lang="chi_sim+eng"):
    try:
        import mss
        import pytesseract
        from PIL import Image
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
                "x": abs_x, "y": abs_y,
                "offset_x": abs_x - x,
                "offset_y": abs_y - y,
            })
        return results
    except Exception:
        return []


def capture_template(x, y, size=TEMPLATE_SIZE, save_dir=None, index=0):
    try:
        import mss
        from PIL import Image
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


class WinRecorder:
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
        self._mouse_hook = None
        self._keyboard_hook = None
        self._hook_thread = None
        self._ocr_queue = []
        self._template_count = 0
        self._template_dir = os.path.join(os.path.dirname(screenshot_dir), "templates")
        self._dragging = False
        self._drag_button = None
        self._drag_last_x = 0
        self._drag_last_y = 0
        self._my_pid = os.getpid()
        os.makedirs(screenshot_dir, exist_ok=True)

    def start(self):
        self.events = []
        self.start_time = time.time()
        self.recording = True
        self._stop_requested = False
        self.screenshot_count = 0
        self.last_screenshot_time = 0
        self._ocr_queue.clear()
        self._template_count = 0
        self._dragging = False
        self._drag_button = None
        logger.info("Windows录制初始化, pid=%d", self._my_pid)

        self._hook_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self._hook_thread.start()

    def stop(self):
        self.recording = False
        self._stop_requested = True
        self._unhook()
        self._process_ocr_queue()
        return self.events

    def should_stop(self):
        return self._stop_requested

    def _unhook(self):
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None
        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None

    def _hook_loop(self):
        def mouse_cb(nCode, wParam, lParam):
            if nCode >= 0 and self.recording:
                info = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents
                x, y = info.x, info.y
                t = time.time() - self.start_time

                if wParam == WM_LBUTTONDOWN:
                    self._on_mouse_down(x, y, "left", t)
                elif wParam == WM_RBUTTONDOWN:
                    self._on_mouse_down(x, y, "right", t)
                elif wParam == WM_MBUTTONDOWN:
                    self._on_mouse_down(x, y, "middle", t)
                elif wParam == WM_LBUTTONUP:
                    self._on_mouse_up(x, y, "left", t)
                elif wParam == WM_RBUTTONUP:
                    self._on_mouse_up(x, y, "right", t)
                elif wParam == WM_MBUTTONUP:
                    self._on_mouse_up(x, y, "middle", t)
                elif wParam == WM_MOUSEWHEEL:
                    delta = ctypes.c_short(info.mouseData >> 16).value
                    self._on_scroll(x, y, delta, t)
                elif wParam == WM_MOUSEMOVE:
                    if self._dragging:
                        self._on_drag(x, y, t)
            return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

        def keyboard_cb(nCode, wParam, lParam):
            if nCode >= 0 and self.recording:
                info = ctypes.cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
                vk = info.vkCode
                t = time.time() - self.start_time
                mods = self._get_modifiers()

                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self._on_key_down(vk, mods, t)
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self._on_key_up(vk, mods, t)
            return user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)

        mouse_proc = HOOKPROC(mouse_cb)
        keyboard_proc = HOOKPROC(keyboard_cb)

        self._mouse_hook = user32.SetWindowsHookExA(WH_MOUSE_LL, mouse_proc, kernel32.GetModuleHandleW(None), 0)
        self._keyboard_hook = user32.SetWindowsHookExA(WH_KEYBOARD_LL, keyboard_proc, kernel32.GetModuleHandleW(None), 0)

        msg = ctypes.wintypes.MSG()
        while not self._stop_requested and user32.GetMessageW(byref(msg), None, 0, 0):
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))

        self._unhook()

    def _get_modifiers(self):
        mods = []
        if user32.GetAsyncKeyState(0x10) & 0x8000:
            mods.append("shift")
        if user32.GetAsyncKeyState(0x11) & 0x8000:
            mods.append("ctrl")
        if user32.GetAsyncKeyState(0x12) & 0x8000:
            mods.append("alt")
        return mods

    def _get_window_info(self, x, y):
        pid, title, cls, bounds = get_window_at_point(x, y)
        return {
            "pid": pid or 0,
            "window": {"owner": title, "title": title, "class": cls},
            "window_bounds": bounds if bounds else {},
        }

    def _on_mouse_down(self, x, y, button, t):
        win = self._get_window_info(x, y)
        ev = {"type": "mouse_down", "x": x, "y": y, "button": button, "time": t}
        ev.update(win)
        if self.ocr_anchors:
            self._ocr_queue.append(("mouse_down", len(self.events), x, y))
        if self.visual_templates:
            tpl = capture_template(x, y, save_dir=self._template_dir, index=self._template_count)
            if tpl:
                ev["template"] = tpl
                self._template_count += 1
        self.events.append(ev)
        self._dragging = True
        self._drag_button = button
        self._drag_last_x = x
        self._drag_last_y = y
        self._maybe_screenshot(t)

    def _on_mouse_up(self, x, y, button, t):
        ev = {"type": "mouse_up", "x": x, "y": y, "button": button, "time": t}
        self.events.append(ev)
        self._dragging = False
        self._drag_button = None

    def _on_drag(self, x, y, t):
        if abs(x - self._drag_last_x) < 5 and abs(y - self._drag_last_y) < 5:
            return
        ev = {"type": "mouse_drag", "x": x, "y": y, "button": self._drag_button, "time": t}
        self.events.append(ev)
        self._drag_last_x = x
        self._drag_last_y = y

    def _on_scroll(self, x, y, delta, t):
        win = self._get_window_info(x, y)
        ev = {"type": "scroll", "x": x, "y": y, "dx": 0, "dy": delta, "time": t}
        ev.update(win)
        self.events.append(ev)

    def _on_key_down(self, vk, mods, t):
        text = ""
        if not mods and 0x20 <= vk <= 0x5A:
            text = chr(vk).lower()
        elif not mods and vk == 0xBD:
            text = "-"
        key_name = VK_MAP.get(vk, f"Key{vk}")

        ev = {"type": "key_down", "keycode": vk, "text": text, "modifiers": mods, "time": t, "key_name": key_name}
        self.events.append(ev)

    def _on_key_up(self, vk, mods, t):
        ev = {"type": "key_up", "keycode": vk, "modifiers": mods, "time": t}
        self.events.append(ev)

    def _maybe_screenshot(self, t):
        if t - self.last_screenshot_time >= self.screenshot_interval:
            self._take_screenshot(t)

    def _take_screenshot(self, t):
        try:
            import mss
            from PIL import Image
            with mss.MSS() as sct:
                screenshot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            fname = f"screenshot_{self.screenshot_count:04d}.png"
            img.save(os.path.join(self.screenshot_dir, fname))
            self.screenshot_count += 1
            self.last_screenshot_time = t
            ev = {"type": "screenshot", "file": fname, "time": t}
            self.events.append(ev)
        except Exception as e:
            logger.warning("截图失败: %s", e)

    def _process_ocr_queue(self):
        if not self.ocr_anchors:
            return
        for event_type, idx, x, y in self._ocr_queue:
            if idx >= len(self.events):
                continue
            results = ocr_at_point(x, y)
            if results:
                best = min(results, key=lambda r: abs(r["offset_x"]) + abs(r["offset_y"]))
                if len(best["text"]) >= 2:
                    self.events[idx]["ocr_anchor"] = {
                        "text": best["text"],
                        "offset_x": best["offset_x"],
                        "offset_y": best["offset_y"],
                    }