import time
import json
import os
import mss

from pynput import mouse, keyboard


class Recorder:
    def __init__(self, screenshot_interval=1.0, screenshot_dir="screenshots"):
        self.events = []
        self.start_time = None
        self.recording = False
        self.screenshot_interval = screenshot_interval
        self.screenshot_dir = screenshot_dir
        self.last_screenshot_time = 0
        self.screenshot_count = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self._stop_key_pressed = False
        os.makedirs(screenshot_dir, exist_ok=True)

    def start(self):
        self.events = []
        self.start_time = time.time()
        self.recording = True
        self._stop_key_pressed = False
        self.screenshot_count = 0
        self.last_screenshot_time = 0

        self.mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self):
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        return self.events

    def is_recording(self):
        return self.recording

    def _elapsed(self):
        return time.time() - self.start_time

    def _take_screenshot(self):
        now = time.time()
        if now - self.last_screenshot_time < self.screenshot_interval:
            return
        self.last_screenshot_time = now
        fname = f"screen_{self.screenshot_count:04d}.png"
        fpath = os.path.join(self.screenshot_dir, fname)
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct.shot(output=fpath)
            self.screenshot_count += 1
            self.events.append({
                "type": "screenshot",
                "file": fname,
                "time": self._elapsed(),
            })
        except Exception:
            pass

    def _on_click(self, x, y, button, pressed):
        if not self.recording:
            return
        self._take_screenshot()
        self.events.append({
            "type": "mouse_click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
            "time": self._elapsed(),
        })

    def _on_scroll(self, x, y, dx, dy):
        if not self.recording:
            return
        self._take_screenshot()
        self.events.append({
            "type": "mouse_scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
            "time": self._elapsed(),
        })

    def _on_press(self, key):
        if not self.recording:
            return
        try:
            key_name = key.char
        except AttributeError:
            key_name = key.name
        if key_name == "f12":
            self._stop_key_pressed = True
            return
        self._take_screenshot()
        self.events.append({
            "type": "key_press",
            "key": key_name,
            "time": self._elapsed(),
        })

    def _on_release(self, key):
        if not self.recording:
            return
        try:
            key_name = key.char
        except AttributeError:
            key_name = key.name
        self.events.append({
            "type": "key_release",
            "key": key_name,
            "time": self._elapsed(),
        })

    def should_stop(self):
        return self._stop_key_pressed