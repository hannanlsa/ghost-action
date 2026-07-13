import logging
import sys

from log_helpers import log_call, log_step, log_error, StepTimer
logger = logging.getLogger("cross_platform")

MAC_KEYCODE_TO_CHAR = {
    0: 'a', 1: 's', 2: 'd', 3: 'f', 4: 'h', 5: 'g', 6: 'z', 7: 'x',
    8: 'c', 9: 'v', 11: 'b', 12: 'q', 13: 'w', 14: 'e', 15: 'r',
    16: 'y', 17: 't', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6',
    23: '5', 24: '=', 25: '9', 26: '7', 27: '-', 28: '8', 29: '0',
    30: ']', 31: 'o', 32: 'u', 33: '[', 34: 'i', 35: 'p',
    37: 'l', 38: ';', 39: "'", 40: 'k', 41: ',', 42: '\\', 43: '/',
    44: 'n', 45: 'm', 46: '.', 47: '\t', 48: ' ', 49: ' ',
    50: '`', 51: '\x1b', 36: '\n',
}

MAC_KEYCODE_TO_VK = {
    0: 0x41, 1: 0x53, 2: 0x44, 3: 0x46, 4: 0x48, 5: 0x47,
    6: 0x5A, 7: 0x58, 8: 0x43, 9: 0x56, 11: 0x42,
    12: 0x51, 13: 0x57, 14: 0x45, 15: 0x52, 16: 0x59, 17: 0x54,
    18: 0x31, 19: 0x32, 20: 0x33, 21: 0x34, 22: 0x36,
    23: 0x35, 24: 0xBB, 25: 0x39, 26: 0x37, 27: 0xBD, 28: 0x38, 29: 0x30,
    30: 0xDD, 31: 0x4F, 32: 0x55, 33: 0xDB, 34: 0x49, 35: 0x50,
    36: 0x0D, 37: 0x4C, 38: 0xBA, 39: 0xDE, 40: 0x4B, 41: 0xBC,
    42: 0xDC, 43: 0xBF, 44: 0x4E, 45: 0x4D, 46: 0xBE,
    47: 0x09, 48: 0x20, 49: 0x20, 50: 0xC0, 51: 0x1B,
    122: 0x70, 123: 0x71, 124: 0x72, 125: 0x73,
    126: 0x74, 127: 0x75,
    0x24: 0x0D,
    0x30: 0x09,
    0x31: 0x20,
    0x33: 0x2E,
    0x35: 0x1B,
    0x7A: 0x70, 0x78: 0x71, 0x63: 0x72, 0x76: 0x73,
    0x60: 0x74, 0x61: 0x75,
}

VK_TO_MAC_KEYCODE = {v: k for k, v in MAC_KEYCODE_TO_VK.items()}

VK_TO_KEY_NAME = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Return", 0x10: "Shift",
    0x11: "Ctrl", 0x12: "Alt", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up",
    0x27: "Right", 0x28: "Down", 0x2C: "PrintScreen", 0x2D: "Insert",
    0x2E: "Delete", 0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
    0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
    0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
    0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}

MAC_MODIFIER_TO_UNIFIED = {
    "cmd": "meta",
    "shift": "shift",
    "ctrl": "ctrl",
    "alt": "alt",
}

UNIFIED_MODIFIER_TO_WIN = {
    "meta": "ctrl",
    "shift": "shift",
    "ctrl": "alt",
    "alt": "alt",
}

UNIFIED_MODIFIER_TO_MAC = {
    "meta": "cmd",
    "shift": "shift",
    "ctrl": "ctrl",
    "alt": "alt",
}

WIN_MODIFIER_TO_UNIFIED = {
    "ctrl": "meta",
    "shift": "shift",
    "alt": "alt",
}

FUNCTION_KEYCODES_MAC = set(range(122, 127)) | {0x24, 0x30, 0x31, 0x33, 0x35, 0x7A, 0x78, 0x63, 0x76, 0x61, 0x60}
FUNCTION_VK_WIN = set(range(0x70, 0x7C)) | {0x08, 0x09, 0x0D, 0x1B, 0x20, 0x2E, 0x24, 0x23, 0x21, 0x22}


def detect_platform():
    return "mac" if sys.platform == "darwin" else "win"


@log_call("CROSS_PLAT", "mac_keycode_to_vk")
def mac_keycode_to_vk(keycode):
    vk = MAC_KEYCODE_TO_VK.get(keycode)
    if vk is not None:
        return vk
    ch = MAC_KEYCODE_TO_CHAR.get(keycode)
    if ch and len(ch) == 1 and ch.isalpha():
        return ord(ch.upper())
    if ch and len(ch) == 1 and 0x20 <= ord(ch) <= 0x5A:
        return ord(ch.upper())
    return None


@log_call("CROSS_PLAT", "vk_to_mac_keycode")
def vk_to_mac_keycode(vk):
    mac_kc = VK_TO_MAC_KEYCODE.get(vk)
    if mac_kc is not None:
        return mac_kc
    if 0x41 <= vk <= 0x5A:
        ch = chr(vk).lower()
        for kc, c in MAC_KEYCODE_TO_CHAR.items():
            if c == ch:
                return kc
    return None


def unify_modifiers(modifiers, source_platform):
    if not modifiers:
        return []
    if source_platform == "mac":
        mapping = MAC_MODIFIER_TO_UNIFIED
    elif source_platform == "win":
        mapping = WIN_MODIFIER_TO_UNIFIED
    else:
        return list(modifiers)
    return [mapping.get(m, m) for m in modifiers]


def modifiers_to_platform(unified_mods, target_platform):
    if not unified_mods:
        return []
    if target_platform == "mac":
        mapping = UNIFIED_MODIFIER_TO_MAC
    elif target_platform == "win":
        mapping = UNIFIED_MODIFIER_TO_WIN
    else:
        return list(unified_mods)
    return [mapping.get(m, m) for m in unified_mods]


@log_call("CROSS_PLAT", "unify_window_info")
def unify_window_info(event, source_platform):
    result = dict(event)
    if source_platform == "mac":
        win = event.get("window")
        if win and isinstance(win, dict):
            bounds = {k: win.get(k) for k in ("x", "y", "width", "height") if k in win}
            info = {k: win.get(k) for k in ("pid", "owner", "title") if k in win}
            if bounds:
                result["window_bounds"] = bounds
            if info:
                result["window_info"] = info
    elif source_platform == "win":
        win_info = event.get("window")
        win_bounds = event.get("window_bounds")
        if win_info and isinstance(win_info, dict):
            flat = {}
            if "owner" in win_info:
                flat["owner"] = win_info["owner"]
            if "title" in win_info:
                flat["title"] = win_info["title"]
            if "class" in win_info:
                flat["class"] = win_info["class"]
            if win_bounds:
                flat.update({k: win_bounds.get(k) for k in ("x", "y", "width", "height") if k in win_bounds})
            elif all(k in win_info for k in ("x", "y", "width", "height")):
                flat.update({k: win_info[k] for k in ("x", "y", "width", "height")})
            result["window"] = flat
    return result


def convert_scroll_delta(dy, source_platform, target_platform):
    if source_platform == target_platform:
        return dy
    if source_platform == "mac" and target_platform == "win":
        return int(dy * 120)
    if source_platform == "win" and target_platform == "mac":
        return dy / 120.0
    return dy


def convert_screenshot_filename(filename, source_platform, target_platform):
    if source_platform == "mac" and target_platform == "win":
        if filename.startswith("screen_"):
            return filename.replace("screen_", "screenshot_", 1)
    elif source_platform == "win" and target_platform == "mac":
        if filename.startswith("screenshot_"):
            return filename.replace("screenshot_", "screen_", 1)
    return filename


def keycode_to_key_name(keycode, platform):
    if platform == "win":
        return VK_TO_KEY_NAME.get(keycode, f"Key{keycode}")
    elif platform == "mac":
        ch = MAC_KEYCODE_TO_CHAR.get(keycode, "")
        if ch and ch.isalpha():
            return ch.upper()
        if keycode in FUNCTION_KEYCODES_MAC:
            if 122 <= keycode <= 127:
                return f"F{keycode - 121}"
            kc_map = {0x24: "Return", 0x30: "Tab", 0x31: "Space",
                      0x33: "Delete", 0x35: "Esc", 0x7A: "F1", 0x78: "F2",
                      0x63: "F3", 0x76: "F4", 0x60: "F5", 0x61: "F6"}
            return kc_map.get(keycode, f"Key{keycode}")
        return ch.upper() if ch else f"Key{keycode}"
    return f"Key{keycode}"


@log_call("CROSS_PLAT", "adapt_event")
def adapt_event(event, source_platform, target_platform):
    if source_platform == target_platform:
        return event

    result = dict(event)
    result["_source_platform"] = source_platform

    etype = event.get("type", "")

    if etype in ("key_down", "key_up"):
        src_keycode = event.get("keycode")
        if src_keycode is not None:
            if source_platform == "mac" and target_platform == "win":
                new_vk = mac_keycode_to_vk(src_keycode)
                if new_vk is not None:
                    result["keycode"] = new_vk
                    result["_original_keycode"] = src_keycode
                    result["key_name"] = VK_TO_KEY_NAME.get(new_vk, f"Key{new_vk}")
                else:
                    result["key_name"] = keycode_to_key_name(src_keycode, "mac")
                    logger.warning("无法映射Mac keycode %d→Win VK, 保留原始值", src_keycode)
            elif source_platform == "win" and target_platform == "mac":
                new_kc = vk_to_mac_keycode(src_keycode)
                if new_kc is not None:
                    result["keycode"] = new_kc
                    result["_original_keycode"] = src_keycode
                else:
                    result["key_name"] = VK_TO_KEY_NAME.get(src_keycode, f"Key{src_keycode}")
                    logger.warning("无法映射Win VK 0x%02X→Mac keycode, 保留原始值", src_keycode)

        src_mods = event.get("modifiers", [])
        if src_mods:
            unified = unify_modifiers(src_mods, source_platform)
            result["modifiers"] = modifiers_to_platform(unified, target_platform)
            result["_original_modifiers"] = src_mods

    elif etype == "scroll":
        src_dy = event.get("dy", 0)
        src_dx = event.get("dx", 0)
        result["dy"] = convert_scroll_delta(src_dy, source_platform, target_platform)
        result["dx"] = convert_scroll_delta(src_dx, source_platform, target_platform)
        result["_original_dy"] = src_dy
        result["_original_dx"] = src_dx

    elif etype == "screenshot":
        src_file = event.get("file", "")
        if src_file:
            result["file"] = convert_screenshot_filename(src_file, source_platform, target_platform)
            result["_original_file"] = src_file

    result = unify_window_info(result, source_platform)

    if etype == "mouse_down":
        if "key_name" not in result:
            kc = result.get("keycode")
            if kc is not None:
                result["key_name"] = keycode_to_key_name(kc, source_platform)

    return result


@log_call("CROSS_PLAT", "adapt_script_events")
def adapt_script_events(events, source_platform, target_platform=None):
    if target_platform is None:
        target_platform = detect_platform()
    if source_platform == target_platform:
        return events
    logger.info("跨平台适配: %s→%s, %d个事件", source_platform, target_platform, len(events))
    adapted = []
    for ev in events:
        adapted.append(adapt_event(ev, source_platform, target_platform))
    key_events = [e for e in adapted if e.get("type") in ("key_down", "key_up")]
    mapped = sum(1 for e in key_events if e.get("_original_keycode") is not None)
    unmapped = sum(1 for e in key_events if e.get("_original_keycode") is None and "keycode" in e)
    scroll_events = [e for e in adapted if e.get("type") == "scroll"]
    logger.info("适配完成: 按键映射=%d, 未映射=%d, 滚动转换=%d", mapped, unmapped, len(scroll_events))
    return adapted


@log_call("CROSS_PLAT", "detect_script_platform")
def detect_script_platform(events):
    if not events:
        return None
    for ev in events:
        p = ev.get("platform")
        if p in ("mac", "win"):
            return p
    for ev in events:
        mods = ev.get("modifiers", [])
        if "cmd" in mods:
            return "mac"
    for ev in events:
        if "window" in ev and "window_bounds" in ev:
            return "win"
    for ev in events:
        win = ev.get("window")
        if isinstance(win, dict) and "class" in win:
            return "win"
        if isinstance(win, dict) and "pid" in win and "owner" in win and "x" in win:
            return "mac"
    for ev in events:
        if ev.get("type") == "screenshot":
            fname = ev.get("file", "")
            if fname.startswith("screen_"):
                return "mac"
            if fname.startswith("screenshot_"):
                return "win"
    mac_score = 0
    win_score = 0
    for ev in events:
        kc = ev.get("keycode")
        if kc is not None:
            if kc in FUNCTION_KEYCODES_MAC:
                mac_score += 2
            elif kc in FUNCTION_VK_WIN and kc not in MAC_KEYCODE_TO_CHAR:
                win_score += 2
            elif 0x41 <= kc <= 0x5A:
                win_score += 1
            elif 0 <= kc <= 51:
                mac_score += 1
            elif kc >= 128:
                win_score += 1
    if mac_score > win_score:
        return "mac"
    if win_score > mac_score:
        return "win"
    return None