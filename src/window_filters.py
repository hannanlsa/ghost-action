import json
import os
import logging
import threading

logger = logging.getLogger("action")

FILTERS_PATH = os.path.expanduser("~/GhostAction/window_filters.json")
_lock = threading.Lock()
_cache = None
_cache_mtime = 0


def _read_filters():
    global _cache, _cache_mtime
    if not os.path.exists(FILTERS_PATH):
        return {"whitelist": [], "blacklist": []}
    try:
        with open(FILTERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"whitelist": [], "blacklist": []}


def get_filters():
    global _cache, _cache_mtime
    with _lock:
        try:
            mtime = os.path.getmtime(FILTERS_PATH)
        except OSError:
            mtime = 0
        if _cache is not None and mtime == _cache_mtime:
            return _cache
        _cache = _read_filters()
        _cache_mtime = mtime
        return _cache


def save_filters(filters):
    global _cache, _cache_mtime
    with _lock:
        os.makedirs(os.path.dirname(FILTERS_PATH), exist_ok=True)
        with open(FILTERS_PATH, "w", encoding="utf-8") as f:
            json.dump(filters, f, ensure_ascii=False, indent=2)
        _cache = filters
        try:
            _cache_mtime = os.path.getmtime(FILTERS_PATH)
        except OSError:
            _cache_mtime = 0


def is_whitelisted(owner, title=""):
    filters = get_filters()
    wl = filters.get("whitelist", [])
    if not wl:
        return False
    combined = f"{owner} {title}".lower()
    return any(w.lower() in combined for w in wl)


def is_blacklisted(owner, title=""):
    filters = get_filters()
    bl = filters.get("blacklist", [])
    if not bl:
        return False
    combined = f"{owner} {title}".lower()
    return any(b.lower() in combined for b in bl)


def get_filter_type(owner, title=""):
    if is_blacklisted(owner, title):
        return "blacklist"
    if is_whitelisted(owner, title):
        return "whitelist"
    return "normal"