import time
import subprocess
import mss
import pytesseract
from PIL import Image
from pynput import mouse, keyboard
from pynput.mouse import Button
from pynput.keyboard import Key


class Player:
    def __init__(self, speed=1.0, mode="coordinate"):
        self.speed = speed
        self.mode = mode
        self.mouse_ctrl = mouse.Controller()
        self.keyboard_ctrl = keyboard.Controller()
        self._stop = False

    def stop(self):
        self._stop = True

    def play(self, events):
        self._stop = False
        if not events:
            return
        start_time = events[0]["time"]
        for event in events:
            if self._stop:
                break
            delay = (event["time"] - start_time) / self.speed
            time.sleep(max(0, delay))
            start_time = event["time"]
            self._execute(event)

    def play_from_file(self, script_path):
        import json
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("events", [])
        self.play(events)

    def _execute(self, event):
        etype = event["type"]
        if etype == "mouse_click":
            self._do_click(event)
        elif etype == "mouse_scroll":
            self._do_scroll(event)
        elif etype == "key_press":
            self._do_key_press(event)
        elif etype == "key_release":
            self._do_key_release(event)
        elif etype == "screenshot":
            pass

    def _do_click(self, event):
        x, y = event["x"], event["y"]
        button = Button.left if event["button"] == "left" else Button.right
        pressed = event["pressed"]
        self.mouse_ctrl.position = (x, y)
        if pressed:
            self.mouse_ctrl.press(button)
        else:
            self.mouse_ctrl.release(button)

    def _do_scroll(self, event):
        x, y = event["x"], event["y"]
        dx, dy = event["dx"], event["dy"]
        self.mouse_ctrl.position = (x, y)
        self.mouse_ctrl.scroll(dx, dy)

    def _do_key_press(self, event):
        key = self._parse_key(event["key"])
        if key:
            self.keyboard_ctrl.press(key)

    def _do_key_release(self, event):
        key = self._parse_key(event["key"])
        if key:
            self.keyboard_ctrl.release(key)

    def _parse_key(self, key_name):
        if len(key_name) == 1:
            return key_name
        key_map = {
            "space": Key.space,
            "enter": Key.enter,
            "tab": Key.tab,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "esc": Key.esc,
            "shift": Key.shift,
            "shift_l": Key.shift_l,
            "shift_r": Key.shift_r,
            "ctrl": Key.ctrl,
            "ctrl_l": Key.ctrl_l,
            "ctrl_r": Key.ctrl_r,
            "alt": Key.alt,
            "alt_l": Key.alt_l,
            "alt_r": Key.alt_r,
            "cmd": Key.cmd,
            "cmd_l": Key.cmd_l,
            "cmd_r": Key.cmd_r,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "home": Key.home,
            "end": Key.end,
            "page_up": Key.page_up,
            "page_down": Key.page_down,
            "caps_lock": Key.caps_lock,
        }
        return key_map.get(key_name, key_name)

    def find_text_on_screen(self, target_text, lang="chi_sim+eng"):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        for i, text in enumerate(data["text"]):
            if target_text.lower() in text.lower():
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                return (x, y)
        return None

    def click_text(self, target_text, lang="chi_sim+eng"):
        pos = self.find_text_on_screen(target_text, lang)
        if pos:
            self.mouse_ctrl.position = pos
            self.mouse_ctrl.click(Button.left)
            return True
        return False