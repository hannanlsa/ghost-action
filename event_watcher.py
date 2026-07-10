import os
import time
import threading
import logging
import json
import platform

IS_MAC = platform.system() == "Darwin"

_WATCHER_FILE = os.path.join(os.path.expanduser("~"), "GhostAction", "watchers.json")

logger = logging.getLogger("event_watcher")


class EventWatcher:
    def __init__(self, on_trigger=None):
        self._watchers = {}
        self._running = False
        self._threads = {}
        self._on_trigger = on_trigger
        self._last_clipboard = ""
        self._load()

    def _load(self):
        if os.path.exists(_WATCHER_FILE):
            try:
                with open(_WATCHER_FILE, "r", encoding="utf-8") as f:
                    self._watchers = json.load(f)
            except Exception as e:
                logger.error("加载监视配置失败: %s", e)
                self._watchers = {}

    def _save(self):
        os.makedirs(os.path.dirname(_WATCHER_FILE), exist_ok=True)
        try:
            tmp = _WATCHER_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._watchers, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _WATCHER_FILE)
        except Exception as e:
            logger.error("保存监视配置失败: %s", e)

    def add_watcher(self, watcher_type, pattern, script_name, enabled=True, params=None):
        wid = f"{watcher_type}_{int(time.time())}"
        self._watchers[wid] = {
            "type": watcher_type,
            "pattern": pattern,
            "script_name": script_name,
            "enabled": enabled,
            "params": params or {},
            "last_triggered": None,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save()
        if self._running:
            self._start_watcher_thread(wid)
        return wid

    def remove_watcher(self, wid):
        if wid in self._watchers:
            del self._watchers[wid]
            self._save()
        if wid in self._threads:
            self._threads[wid]["stop"] = True

    def toggle_watcher(self, wid):
        if wid not in self._watchers:
            return False
        self._watchers[wid]["enabled"] = not self._watchers[wid]["enabled"]
        self._save()
        return self._watchers[wid]["enabled"]

    def list_watchers(self):
        return dict(self._watchers)

    def start(self, on_trigger=None):
        if on_trigger:
            self._on_trigger = on_trigger
        self._running = True
        for wid in self._watchers:
            if self._watchers[wid].get("enabled", True):
                self._start_watcher_thread(wid)
        logger.info("事件监视器已启动, %d个规则", len(self._watchers))

    def stop(self):
        self._running = False
        for wid in list(self._threads.keys()):
            self._threads[wid]["stop"] = True
        self._threads.clear()
        logger.info("事件监视器已停止")

    def _start_watcher_thread(self, wid):
        if wid in self._threads:
            self._threads[wid]["stop"] = True
        t = threading.Thread(target=self._watcher_loop, args=(wid,), daemon=True)
        self._threads[wid] = {"thread": t, "stop": False}
        t.start()

    def _watcher_loop(self, wid):
        w = self._watchers.get(wid)
        if not w:
            return
        wtype = w.get("type", "")
        if wtype == "file":
            self._file_watch_loop(wid)
        elif wtype == "clipboard":
            self._clipboard_watch_loop(wid)
        elif wtype == "window":
            self._window_watch_loop(wid)

    def _file_watch_loop(self, wid):
        w = self._watchers.get(wid)
        if not w:
            return
        path = w.get("pattern", "")
        if not path:
            return
        last_mtime = 0
        if os.path.exists(path):
            try:
                last_mtime = os.path.getmtime(path)
            except OSError:
                pass

        while self._running and not self._threads.get(wid, {}).get("stop"):
            if not w.get("enabled", True):
                time.sleep(5)
                continue
            try:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    if mtime > last_mtime:
                        last_mtime = mtime
                        logger.info("文件变化触发: %s → %s", path, w["script_name"])
                        self._trigger(wid)
                        time.sleep(2)
                else:
                    if os.path.isdir(os.path.dirname(path) or path):
                        parent = path if os.path.isdir(path) else os.path.dirname(path)
                        try:
                            entries = set(os.listdir(parent))
                            time.sleep(2)
                            new_entries = set(os.listdir(parent))
                            if new_entries != entries:
                                logger.info("目录变化触发: %s → %s", parent, w["script_name"])
                                self._trigger(wid)
                                time.sleep(2)
                        except OSError:
                            pass
            except Exception as e:
                logger.error("文件监视错误: %s", e)
            time.sleep(3)

    def _clipboard_watch_loop(self, wid):
        w = self._watchers.get(wid)
        if not w:
            return
        pattern = w.get("pattern", "").lower()
        last_content = ""

        while self._running and not self._threads.get(wid, {}).get("stop"):
            if not w.get("enabled", True):
                time.sleep(5)
                continue
            try:
                content = self._read_clipboard()
                if content and content != last_content:
                    last_content = content
                    if not pattern or pattern in content.lower():
                        logger.info("剪贴板触发: 匹配'%s' → %s", pattern, w["script_name"])
                        self._trigger(wid)
                        time.sleep(2)
            except Exception as e:
                logger.error("剪贴板监视错误: %s", e)
            time.sleep(1)

    def _window_watch_loop(self, wid):
        w = self._watchers.get(wid)
        if not w:
            return
        pattern = w.get("pattern", "").lower()
        last_frontmost = ""

        while self._running and not self._threads.get(wid, {}).get("stop"):
            if not w.get("enabled", True):
                time.sleep(5)
                continue
            try:
                frontmost = self._get_frontmost_window()
                if frontmost and frontmost != last_frontmost:
                    last_frontmost = frontmost
                    if not pattern or pattern in frontmost.lower():
                        logger.info("窗口触发: '%s' 匹配'%s' → %s", frontmost, pattern, w["script_name"])
                        self._trigger(wid)
                        time.sleep(3)
            except Exception as e:
                logger.error("窗口监视错误: %s", e)
            time.sleep(2)

    def _trigger(self, wid):
        w = self._watchers.get(wid)
        if not w:
            return
        self._watchers[wid]["last_triggered"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        if self._on_trigger:
            try:
                self._on_trigger(w["script_name"], w.get("params", {}))
            except Exception as e:
                logger.error("事件触发执行失败 %s: %s", wid, e)

    def _read_clipboard(self):
        try:
            if IS_MAC:
                import subprocess
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
                return result.stdout[:10000]
            else:
                import subprocess
                result = subprocess.run(["powershell", "-command", "Get-Clipboard"],
                                       capture_output=True, text=True, timeout=2)
                return result.stdout[:10000]
        except Exception:
            return ""

    def _get_frontmost_window(self):
        try:
            if IS_MAC:
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2)
                return result.stdout.strip()
            else:
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
                    buf = ctypes.create_unicode_buffer(length)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
                    return buf.value
        except Exception:
            return ""