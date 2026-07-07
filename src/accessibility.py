import logging
from ApplicationServices import (
    AXUIElementCreateApplication, AXUIElementCopyElementAtPosition,
    AXUIElementCopyAttributeValue, AXUIElementCopyActionNames,
    AXUIElementPerformAction, AXUIElementSetAttributeValue,
    kAXErrorSuccess, kAXErrorAPIDisabled, kAXErrorNotImplemented,
    kAXErrorInvalidUIElement, kAXErrorCannotComplete,
)
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

logger = logging.getLogger("accessibility")

ATTRS_TO_CAPTURE = [
    "AXRole", "AXTitle", "AXDescription", "AXValue", "AXIdentifier",
    "AXRoleDescription", "AXHelp",
]


def _ax_error_name(err):
    names = {
        0: "success", -25200: "api_disabled", -25201: "not_implemented",
        -25202: "invalid_ui_element", -25203: "cannot_complete",
        -25204: "attribute_unsupported", -25205: "action_unsupported",
        -25206: "notification_unsupported", -25207: "not_enough_precision",
        -25208: "parameterized_attribute_unsupported", -25210: "no_value",
    }
    return names.get(err, f"unknown({err})")


def get_element_at_point(pid, x, y):
    try:
        app = AXUIElementCreateApplication(pid)
        err, element = AXUIElementCopyElementAtPosition(app, float(x), float(y), None)
        if err != kAXErrorSuccess:
            logger.debug("获取元素失败: pid=%d (%.0f,%.0f) err=%s", pid, x, y, _ax_error_name(err))
            return None
        return element
    except Exception as e:
        logger.debug("获取元素异常: %s (pid=%d x=%.0f y=%.0f)", e, pid, x, y)
        import traceback
        logger.debug("堆栈: %s", traceback.format_exc())
        return None


def get_element_attrs(element):
    if not element:
        return None
    result = {}
    for attr in ATTRS_TO_CAPTURE:
        try:
            err, val = AXUIElementCopyAttributeValue(element, attr, None)
            if err == kAXErrorSuccess and val:
                result[attr] = str(val)
        except Exception:
            pass
    try:
        err, pos = AXUIElementCopyAttributeValue(element, "AXPosition", None)
        if err == kAXErrorSuccess and pos:
            result["AXPosition"] = {"x": float(pos.x), "y": float(pos.y)}
    except Exception:
        pass
    try:
        err, size = AXUIElementCopyAttributeValue(element, "AXSize", None)
        if err == kAXErrorSuccess and size:
            result["AXSize"] = {"w": float(size.width), "h": float(size.height)}
    except Exception:
        pass
    return result if result else None


def get_element_actions(element):
    if not element:
        return []
    try:
        err, actions = AXUIElementCopyActionNames(element, None)
        if err == kAXErrorSuccess and actions:
            return [str(a) for a in actions]
    except Exception:
        pass
    return []


def find_element_by_attrs(pid, attrs, timeout=5):
    import time
    app = AXUIElementCreateApplication(pid)
    start = time.time()
    while time.time() - start < timeout:
        result = _find_in_tree(app, attrs)
        if result:
            return result
        time.sleep(0.3)
    return None


def _find_in_tree(element, target_attrs, depth=0, max_depth=8):
    if depth > max_depth:
        return None
    attrs = get_element_attrs(element)
    if attrs:
        match = True
        for key, val in target_attrs.items():
            if key not in attrs or attrs[key] != val:
                match = False
                break
        if match:
            return element
    try:
        err, children = AXUIElementCopyAttributeValue(element, "AXChildren", None)
        if err == kAXErrorSuccess and children:
            for child in children:
                result = _find_in_tree(child, target_attrs, depth + 1, max_depth)
                if result:
                    return result
    except Exception:
        pass
    return None


def perform_action(element, action="AXPress"):
    if not element:
        return False
    try:
        err = AXUIElementPerformAction(element, action, None)
        if err == kAXErrorSuccess:
            logger.info("执行动作: %s", action)
            return True
        logger.warning("执行动作失败: %s err=%s", action, _ax_error_name(err))
        return False
    except Exception as e:
        logger.warning("执行动作异常: %s", e)
        return False


def set_value(element, value):
    if not element:
        return False
    try:
        err = AXUIElementSetAttributeValue(element, "AXValue", value, None)
        if err == kAXErrorSuccess:
            logger.info("设置值: %s", value)
            return True
        return False
    except Exception as e:
        logger.warning("设置值异常: %s", e)
        return False


def get_pid_for_app(app_name):
    try:
        wl = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in wl:
            owner = w.get('kCGWindowOwnerName', '')
            if owner == app_name:
                return w.get('kCGWindowOwnerPID', -1)
    except Exception:
        pass
    return -1