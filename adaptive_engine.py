import time
import logging
import os
import platform

IS_MAC = platform.system() == "Darwin"

logger = logging.getLogger("adaptive_engine")


class AdaptiveEngine:
    def __init__(self, scripts_dir=None, use_ai_fallback=True):
        self.scripts_dir = scripts_dir or os.path.join(os.path.expanduser("~"), "GhostAction")
        self.use_ai_fallback = use_ai_fallback
        self._recorded_bounds = {}
        self._screen_size = self._get_screen_size()
        self._last_screenshot = None
        self._last_screenshot_time = 0

    def _get_screen_size(self):
        try:
            if IS_MAC:
                from Quartz import CGMainDisplayID, CGDisplayPixelsWide, CGDisplayPixelsHigh
                mid = CGMainDisplayID()
                return (CGDisplayPixelsWide(mid), CGDisplayPixelsHigh(mid))
            else:
                import ctypes
                user32 = ctypes.windll.user32
                return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        except Exception:
            return (1920, 1080)

    def record_window_bounds(self, pid, bounds):
        self._recorded_bounds[pid] = bounds

    def adapt_coordinates(self, x, y, recorded_bounds, current_bounds):
        if not recorded_bounds or not current_bounds:
            return x, y
        rw = recorded_bounds.get("width", 0)
        rh = recorded_bounds.get("height", 0)
        cw = current_bounds.get("width", 0)
        ch = current_bounds.get("height", 0)
        if rw <= 0 or rh <= 0 or cw <= 0 or ch <= 0:
            return x, y
        rx = x - recorded_bounds.get("x", 0)
        ry = y - recorded_bounds.get("y", 0)
        scale_x = cw / rw
        scale_y = ch / rh
        nx = current_bounds.get("x", 0) + rx * scale_x
        ny = current_bounds.get("y", 0) + ry * scale_y
        return nx, ny

    def smart_wait(self, strategy, timeout=10, interval_start=0.3, interval_max=2.0,
                   template_path=None, ocr_text=None, check_fn=None, **kwargs):
        start = time.time()
        interval = interval_start
        attempt = 0
        if strategy == "pixel_change":
            self._last_screenshot = None
            self._last_screenshot_time = 0
        while time.time() - start < timeout:
            if check_fn:
                try:
                    if check_fn():
                        return True
                except Exception:
                    pass
            elif strategy == "template" and template_path:
                if self._check_template(template_path):
                    return True
            elif strategy == "ocr" and ocr_text:
                if self._check_ocr(ocr_text):
                    return True
            elif strategy == "pixel_change":
                if self._check_pixel_change():
                    return True
            elif strategy == "loading_gone":
                if self._check_loading_gone():
                    return True
            elif strategy == "element_visible":
                if self._check_element_visible(kwargs.get("ax_role", ""), kwargs.get("ax_title", "")):
                    return True
            elapsed = time.time() - start
            if elapsed > timeout * 0.5:
                interval = min(interval * 1.5, interval_max)
            attempt += 1
            time.sleep(interval)
        return False

    def _check_template(self, template_path):
        try:
            import cv2
            import numpy as np
            if not os.path.exists(template_path):
                return False
            screenshot = self._take_screenshot()
            if screenshot is None:
                return False
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                return False
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val >= 0.55
        except Exception:
            return False

    def _check_ocr(self, text):
        try:
            import pytesseract
            from PIL import Image
            screenshot = self._take_screenshot_pil()
            if screenshot is None:
                return False
            ocr_result = pytesseract.image_to_string(screenshot, lang="chi_sim+eng")
            return text.lower() in ocr_result.lower()
        except Exception:
            return False

    def _check_pixel_change(self):
        try:
            from PIL import Image
            import numpy as np
            current = self._take_screenshot_pil()
            if current is None:
                return True
            if self._last_screenshot is None:
                self._last_screenshot = current
                self._last_screenshot_time = time.time()
                return False
            if time.time() - self._last_screenshot_time < 1.0:
                return False
            arr1 = np.array(self._last_screenshot.resize((320, 180)))
            arr2 = np.array(current.resize((320, 180)))
            diff = np.abs(arr1.astype(float) - arr2.astype(float)).mean()
            self._last_screenshot = current
            self._last_screenshot_time = time.time()
            return diff < 5.0
        except Exception:
            return True

    def _check_loading_gone(self):
        loading_indicators = ["loading", "加载", "请稍候", "spinner", "progress"]
        try:
            import pytesseract
            from PIL import Image
            screenshot = self._take_screenshot_pil()
            if screenshot is None:
                return True
            ocr_result = pytesseract.image_to_string(screenshot, lang="chi_sim+eng").lower()
            for indicator in loading_indicators:
                if indicator in ocr_result:
                    return False
            return True
        except Exception:
            return True

    def _check_element_visible(self, ax_role, ax_title):
        if not IS_MAC:
            return True
        try:
            from ApplicationServices import AXUIElementCreateApplication, AXUIElementCopyAttributeValue
            apps = self._get_frontmost_app_pid()
            if not apps:
                return True
            ax_app = AXUIElementCreateApplication(apps)
            try:
                err, value = AXUIElementCopyAttributeValue(ax_app, "AXFocusedWindow", None)
            except Exception:
                return True
            if not value:
                return True
            return self._search_ax_element(value, ax_role, ax_title, depth=0)
        except Exception:
            return True

    def _search_ax_element(self, element, ax_role, ax_title, depth=0):
        if depth > 5:
            return False
        try:
            err, children = AXUIElementCopyAttributeValue(element, "AXChildren", None)
            if not children:
                return False
            for child in children:
                try:
                    err, role = AXUIElementCopyAttributeValue(child, "AXRole", None)
                    err, title = AXUIElementCopyAttributeValue(child, "AXTitle", None)
                    if ax_role and role == ax_role:
                        return True
                    if ax_title and title and ax_title in title:
                        return True
                    if self._search_ax_element(child, ax_role, ax_title, depth + 1):
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _get_frontmost_app_pid(self):
        try:
            if IS_MAC:
                from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListOptionOnScreenOnly
                windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
                for w in windows:
                    if w.get("kCGWindowLayer", 1) == 0 and w.get("kCGWindowOwnerPID"):
                        return w["kCGWindowOwnerPID"]
        except Exception:
            pass
        return None

    def find_alternative_path(self, event, failed_method):
        alternatives = []
        etype = event.get("type", "")
        if etype == "mouse_down":
            ax = event.get("ax_element", {})
            ax_actions = event.get("ax_actions", [])
            if "AXPress" in ax_actions:
                alternatives.append(("accessibility_press", ax))
            ocr = event.get("ocr_anchor", {})
            if ocr.get("text") and len(ocr["text"]) >= 2:
                alternatives.append(("ocr_click", ocr))
            dom = event.get("dom_selector", {})
            if dom.get("selectors"):
                alternatives.append(("dom_click", dom))
            if self.use_ai_fallback:
                alternatives.append(("ai_locate", event))
        elif etype == "type_text":
            text = event.get("text", "")
            dom = event.get("dom_selector", {})
            if dom.get("selectors"):
                alternatives.append(("dom_fill", (dom, text)))
        return alternatives

    def execute_alternative(self, alt_type, alt_data, browser_engine=None, browser_profile=None, pid=None):
        if alt_type == "accessibility_press":
            return self._alt_accessibility_press(alt_data, pid=pid)
        elif alt_type == "ocr_click":
            return self._alt_ocr_click(alt_data)
        elif alt_type == "dom_click":
            return self._alt_dom_click(alt_data, browser_engine, browser_profile)
        elif alt_type == "dom_fill":
            return self._alt_dom_fill(alt_data, browser_engine, browser_profile)
        elif alt_type == "ai_locate":
            return self._alt_ai_locate(alt_data)
        return False

    def _alt_accessibility_press(self, ax_data, pid=None):
        if not IS_MAC:
            return False
        try:
            from accessibility import find_element_by_attrs
            ax_role = ax_data.get("AXRole", "")
            ax_title = ax_data.get("AXTitle", "")
            ax_desc = ax_data.get("AXDescription", "")
            elem = find_element_by_attrs(pid=pid, role=ax_role, title=ax_title, description=ax_desc)
            if elem:
                from ApplicationServices import AXUIElementPerformAction
                AXUIElementPerformAction(elem, "AXPress")
                logger.info("替代路径: Accessibility AXPress成功")
                return True
        except Exception as e:
            logger.warning("替代路径Accessibility失败: %s", e)
        return False

    def _alt_ocr_click(self, ocr_data):
        try:
            import pytesseract
            from PIL import Image
            text = ocr_data.get("text", "")
            offset_x = ocr_data.get("offset_x", 0)
            offset_y = ocr_data.get("offset_y", 0)
            screenshot = self._take_screenshot_pil()
            if screenshot is None:
                return False
            data = pytesseract.image_to_data(screenshot, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
            for i, t in enumerate(data["text"]):
                if text.lower() in t.lower() and len(t) >= 2:
                    cx = data["left"][i] + data["width"][i] // 2 + offset_x
                    cy = data["top"][i] + data["height"][i] // 2 + offset_y
                    self._click_at(cx, cy)
                    logger.info("替代路径: OCR点击成功 '%s' at (%d,%d)", text, cx, cy)
                    return True
        except Exception as e:
            logger.warning("替代路径OCR点击失败: %s", e)
        return False

    def _alt_dom_click(self, dom_data, browser_engine, browser_profile):
        if not browser_engine or not browser_engine.is_connected():
            return False
        try:
            page = browser_engine.get_page(browser_profile)
            for sel in dom_data.get("selectors", []):
                if browser_engine.dom_click(page, sel, timeout=3000):
                    logger.info("替代路径: DOM点击成功 '%s'", sel)
                    return True
        except Exception as e:
            logger.warning("替代路径DOM点击失败: %s", e)
        return False

    def _alt_dom_fill(self, fill_data, browser_engine, browser_profile):
        if not browser_engine or not browser_engine.is_connected():
            return False
        try:
            dom, text = fill_data
            page = browser_engine.get_page(browser_profile)
            for sel in dom.get("selectors", []):
                if browser_engine.dom_fill(page, sel, text, timeout=3000):
                    logger.info("替代路径: DOM填充成功 '%s'", sel)
                    return True
        except Exception as e:
            logger.warning("替代路径DOM填充失败: %s", e)
        return False

    def _alt_ai_locate(self, event):
        try:
            import ai_recognizer
            ax = event.get("ax_element", {})
            target = ax.get("AXTitle") or ax.get("AXRoleDescription") or event.get("ocr_anchor", {}).get("text", "")
            if not target:
                return False
            screenshot_path = self._save_screenshot_temp()
            if not screenshot_path:
                return False
            result = ai_recognizer.locate_on_screen_with_fallback(screenshot_path, target)
            if result and len(result) >= 2:
                self._click_at(result[0], result[1])
                logger.info("替代路径: AI定位点击成功 '%s' at (%s,%s)", target, result[0], result[1])
                return True
        except Exception as e:
            logger.warning("替代路径AI定位失败: %s", e)
        return False

    def _take_screenshot(self):
        try:
            import cv2
            import numpy as np
            if IS_MAC:
                from Quartz import CGWindowListCreateImage, kCGNullWindowID, kCGWindowListOptionOnScreenOnly, CGRectNull
                cg_img = CGWindowListCreateImage(CGRectNull, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, 0)
                if cg_img:
                    from Quartz import CGImageGetWidth, CGImageGetHeight, CGImageGetBytesPerRow, CGImageGetDataProvider
                    from Quartz import CGDataProviderCopyData
                    w = CGImageGetWidth(cg_img)
                    h = CGImageGetHeight(cg_img)
                    bpr = CGImageGetBytesPerRow(cg_img)
                    data = CGDataProviderCopyData(CGImageGetDataProvider(cg_img))
                    arr = np.frombuffer(data, dtype=np.uint8).reshape(h, bpr // 4, 4)
                    return cv2.cvtColor(arr[:, :w, :3], cv2.COLOR_RGBA2BGR)
            else:
                import mss
                with mss.mss() as sct:
                    shot = sct.grab(sct.monitors[0])
                    arr = np.array(shot)
                    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def _take_screenshot_pil(self):
        try:
            if IS_MAC:
                from Quartz import CGWindowListCreateImage, kCGNullWindowID, kCGWindowListOptionOnScreenOnly, CGRectNull
                cg_img = CGWindowListCreateImage(CGRectNull, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, 0)
                if cg_img:
                    from PIL import Image
                    from Quartz import CGImageGetWidth, CGImageGetHeight, CGImageGetBytesPerRow, CGImageGetDataProvider
                    from Quartz import CGDataProviderCopyData
                    import numpy as np
                    w = CGImageGetWidth(cg_img)
                    h = CGImageGetHeight(cg_img)
                    bpr = CGImageGetBytesPerRow(cg_img)
                    data = CGDataProviderCopyData(CGImageGetDataProvider(cg_img))
                    arr = np.frombuffer(data, dtype=np.uint8).reshape(h, bpr // 4, 4)
                    return Image.fromarray(arr[:, :w, :3], "RGBA")
            else:
                import mss
                from PIL import Image
                with mss.mss() as sct:
                    shot = sct.grab(sct.monitors[0])
                    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        except Exception:
            return None

    def _save_screenshot_temp(self):
        try:
            from PIL import Image
            img = self._take_screenshot_pil()
            if img is None:
                return None
            path = os.path.join(self.scripts_dir, "tmp_screenshot.png")
            img.save(path)
            return path
        except Exception:
            return None

    def _click_at(self, x, y):
        if IS_MAC:
            try:
                from Quartz import CGEventCreateMouseEvent, CGEventPost, kCGHIDEventTap
                from Quartz import kCGEventMouseMoved, kCGEventLeftMouseDown, kCGEventLeftMouseUp
                from Quartz import kCGMouseButtonLeft, kCGEventSourceStateHIDSystemState
                from Quartz import CGEventSourceCreate
                src = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
                move = CGEventCreateMouseEvent(src, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft)
                down = CGEventCreateMouseEvent(src, kCGEventLeftMouseDown, (x, y), kCGMouseButtonLeft)
                up = CGEventCreateMouseEvent(src, kCGEventLeftMouseUp, (x, y), kCGMouseButtonLeft)
                CGEventPost(kCGHIDEventTap, move)
                time.sleep(0.05)
                CGEventPost(kCGHIDEventTap, down)
                time.sleep(0.05)
                CGEventPost(kCGHIDEventTap, up)
            except Exception as e:
                logger.error("替代路径点击失败: %s", e)
        else:
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(int(x), int(y))
                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
            except Exception as e:
                logger.error("替代路径点击失败: %s", e)