import os
import json
import time
import logging
import hashlib
import random
import string
import sys
import subprocess
from pathlib import Path

logger = logging.getLogger("browser_engine")

PROFILES_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "browser_profiles")


def _find_bundled_chromium():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
        candidates = [
            os.path.join(base, "chromium", "chrome-mac-arm64", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(base, "chromium", "chrome-mac", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(base, "chromium", "chrome-win", "chrome.exe"),
            os.path.join(base, "chromium", "chrome-linux", "chrome"),
        ]
    else:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(src_dir)
        candidates = [
            os.path.join(base, "chromium", "chrome-mac-arm64", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(base, "chromium", "chrome-mac", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing"),
            os.path.join(base, "chromium", "chrome-win", "chrome.exe"),
            os.path.join(base, "chromium", "chrome-linux", "chrome"),
        ]
    for c in candidates:
        if os.path.exists(c):
            logger.info(f"[browser] found bundled chromium: {c}")
            return c
    return None


def _find_playwright_chromium():
    try:
        cache_dir = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
        if not os.path.exists(cache_dir):
            return None
        for d in sorted(os.listdir(cache_dir), reverse=True):
            if d.startswith("chromium-") and not d.startswith("chromium_headless"):
                full = os.path.join(cache_dir, d)
                if sys.platform == "darwin":
                    exe = os.path.join(full, "chrome-mac-arm64", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")
                    if not os.path.exists(exe):
                        exe = os.path.join(full, "chrome-mac", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing")
                elif sys.platform == "win32":
                    exe = os.path.join(full, "chrome-win", "chrome.exe")
                else:
                    exe = os.path.join(full, "chrome-linux", "chrome")
                if os.path.exists(exe):
                    return exe
    except Exception:
        pass
    return None


def get_chromium_path():
    return _find_bundled_chromium() or _find_playwright_chromium()


def _ensure_profiles_dir():
    os.makedirs(PROFILES_DIR, exist_ok=True)


def list_profiles():
    _ensure_profiles_dir()
    profiles = []
    for d in os.listdir(PROFILES_DIR):
        p = os.path.join(PROFILES_DIR, d)
        if os.path.isdir(p) and d.endswith(".profile"):
            meta_path = os.path.join(p, "meta.json")
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                except Exception:
                    pass
            profiles.append({
                "id": d.replace(".profile", ""),
                "name": meta.get("name", d.replace(".profile", "")),
                "path": p,
                "ua": meta.get("user_agent", ""),
                "created": meta.get("created", ""),
            })
    return profiles


def create_profile(name=None):
    _ensure_profiles_dir()
    pid = name or "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    profile_dir = os.path.join(PROFILES_DIR, f"{pid}.profile")
    os.makedirs(profile_dir, exist_ok=True)
    meta = {
        "name": pid,
        "user_agent": _generate_ua(),
        "viewport": {"width": random.choice([1280, 1366, 1440, 1536, 1920]),
                      "height": random.choice([720, 768, 900, 1024, 1080])},
        "locale": random.choice(["zh-CN", "en-US", "zh-TW"]),
        "timezone": random.choice(["Asia/Shanghai", "America/New_York", "Asia/Tokyo"]),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(profile_dir, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    logger.info(f"[browser] created profile: {pid}")
    return {"id": pid, "path": profile_dir, "meta": meta}


def delete_profile(profile_id):
    import shutil
    p = os.path.join(PROFILES_DIR, f"{profile_id}.profile")
    if os.path.exists(p):
        shutil.rmtree(p)
        logger.info(f"[browser] deleted profile: {profile_id}")


def _generate_ua():
    chrome_versions = ["120.0.6099.109", "121.0.6167.85", "122.0.6261.94",
                       "123.0.6312.58", "124.0.6367.91", "125.0.6422.76",
                       "126.0.6478.114", "127.0.6533.72", "128.0.6613.85"]
    cv = random.choice(chrome_versions)
    platforms = [
        f"Windows NT 10.0; Win64; x64",
        f"Macintosh; Intel Mac OS X 10_15_7",
        f"Macintosh; Intel Mac OS X 14_0",
        f"X11; Linux x86_64",
    ]
    plat = random.choice(platforms)
    return f"Mozilla/5.0 ({plat}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{cv} Safari/537.36"


STEALTH_JS = """
// Canvas fingerprint noise
const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === undefined) type = 'image/png';
    const ctx = this.getContext('2d');
    if (ctx && this.width > 0 && this.height > 0) {
        const imgData = ctx.getImageData(0, 0, 1, 1);
        imgData.data[0] = imgData.data[0] ^ 1;
        ctx.putImageData(imgData, 0, 0);
    }
    return _origToDataURL.apply(this, arguments);
};

const _origToBlob = HTMLCanvasElement.prototype.toBlob;
HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
    if (type === undefined) type = 'image/png';
    const ctx = this.getContext('2d');
    if (ctx && this.width > 0 && this.height > 0) {
        const imgData = ctx.getImageData(0, 0, 1, 1);
        imgData.data[0] = imgData.data[0] ^ 1;
        ctx.putImageData(imgData, 0, 0);
    }
    return _origToBlob.apply(this, arguments);
};

// WebGL fingerprint noise
const _origGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(param) {
    if (param === 37445) return 'Google Inc. (NVIDIA)';
    if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    if (param === 7937) return 'WebKit WebGL';
    if (param === 7938) return 'WebKit WebGL';
    return _origGetParameter.apply(this, arguments);
};

if (typeof WebGL2RenderingContext !== 'undefined') {
    const _origGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Google Inc. (NVIDIA)';
        if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        if (param === 7937) return 'WebKit WebGL';
        if (param === 7938) return 'WebKit WebGL';
        return _origGetParameter2.apply(this, arguments);
    };
}

// AudioContext fingerprint noise
const _origGetChannelData = AudioBuffer.prototype.getChannelData;
AudioBuffer.prototype.getChannelData = function(channel) {
    const data = _origGetChannelData.apply(this, arguments);
    if (data && data.length > 0) {
        data[0] += 0.0001 * (Math.random() - 0.5);
    }
    return data;
};

const _origCreateAnalyser = AudioContext.prototype.createAnalyser;
AudioContext.prototype.createAnalyser = function() {
    const analyser = _origCreateAnalyser.apply(this, arguments);
    const _origGetFloatFreqData = analyser.getFloatFrequencyData;
    analyser.getFloatFrequencyData = function(array) {
        _origGetFloatFreqData.apply(this, arguments);
        if (array && array.length > 0) {
            array[0] += 0.01 * (Math.random() - 0.5);
        }
    };
    return analyser;
};

// Navigator properties
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

// Remove automation indicators
delete navigator.__proto__.webdriver;
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Permissions
const _origQuery = window.Permissions.prototype.query;
window.Permissions.prototype.query = function(parameters) {
    if (parameters.name === 'notifications') {
        return Promise.resolve({state: Notification.permission});
    }
    return _origQuery.apply(this, arguments);
};

// Chrome runtime
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {connect: function(){}, sendMessage: function(){}};
}

// Plugin/mimeType
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en']
});
"""


class BrowserEngine:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._contexts = {}
        self._pages = {}
        self._connected = False
        self._session_counter = 0
        self._chromium_ready = None

    def _get_playwright(self):
        if self._pw is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
        return self._pw

    def _check_chromium(self):
        if self._chromium_ready is not None:
            return self._chromium_ready
        try:
            from playwright.sync_api import sync_playwright
            self._chromium_ready = get_chromium_path() is not None
        except ImportError:
            self._chromium_ready = False
        return self._chromium_ready

    def _install_chromium(self):

        logger.info("[browser] installing chromium...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                self._chromium_ready = True
                logger.info("[browser] chromium installed successfully")
                return True
            else:
                logger.error(f"[browser] chromium install failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"[browser] chromium install error: {e}")
            return False

    def _ensure_browser(self, headless=False):
        if self._browser and self._browser.is_connected():
            return True
        chromium_path = get_chromium_path()
        if not chromium_path:
            if not self._install_chromium():
                return False
            chromium_path = get_chromium_path()
        pw = self._get_playwright()
        try:
            launch_opts = {
                "headless": headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }
            if chromium_path:
                launch_opts["executable_path"] = chromium_path
            self._browser = pw.chromium.launch(**launch_opts)
            self._connected = True
            logger.info("[browser] chromium launched (shared, path=%s)", chromium_path or "playwright default")
            return True
        except Exception as e:
            logger.error(f"[browser] launch failed: {e}")
            return False

    def is_available(self):
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False

    def new_identity(self, headless=False):
        self._session_counter += 1
        session_id = f"identity-{self._session_counter}"

        if not self._ensure_browser(headless=headless):
            return None, None

        profile = create_profile(session_id)
        meta = profile.get("meta", {})

        ctx_options = {}
        if meta.get("user_agent"):
            ctx_options["user_agent"] = meta["user_agent"]
        if meta.get("viewport"):
            ctx_options["viewport"] = meta["viewport"]
        if meta.get("locale"):
            ctx_options["locale"] = meta["locale"]
        if meta.get("timezone"):
            ctx_options["timezone_id"] = meta["timezone"]

        context = self._browser.new_context(**ctx_options)
        context.add_init_script(STEALTH_JS)

        page = context.new_page()

        self._contexts[session_id] = context
        self._pages[session_id] = page

        logger.info(f"[browser] new identity: {session_id}, ua={meta.get('user_agent', 'default')[:50]}...")
        return session_id, page

    def close_identity(self, session_id):
        if session_id in self._contexts:
            try:
                self._contexts[session_id].close()
            except Exception:
                pass
            del self._contexts[session_id]
            if session_id in self._pages:
                del self._pages[session_id]
            logger.info(f"[browser] closed identity: {session_id}")
        if not self._contexts and self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
            self._connected = False
            logger.info("[browser] all identities closed, browser released")

    def connect_cdp(self, cdp_url="http://localhost:9222"):
        pw = self._get_playwright()
        try:
            self._browser = pw.chromium.connect_over_cdp(cdp_url)
            self._connected = True
            logger.info(f"[browser] connected CDP: {cdp_url}")
            return self._browser
        except Exception as e:
            logger.error(f"[browser] CDP connect failed: {e}")
            return None

    def get_page(self, session_id=None):
        if session_id and session_id in self._pages:
            return self._pages[session_id]
        if self._pages:
            return next(iter(self._pages.values()))
        return None

    def get_active_session_id(self):
        if self._pages:
            return next(iter(self._pages.keys()))
        return None

    def list_sessions(self):
        result = []
        for sid, page in self._pages.items():
            url = ""
            try:
                url = page.url
            except Exception:
                pass
            result.append({"id": sid, "url": url})
        return result

    def dom_click(self, page, selector, timeout=5000):
        try:
            page.click(selector, timeout=timeout)
            logger.info(f"[browser] DOM click: {selector}")
            return True
        except Exception as e:
            logger.warning(f"[browser] DOM click failed: {selector} -> {e}")
            return False

    def dom_fill(self, page, selector, value, timeout=5000):
        try:
            page.fill(selector, value, timeout=timeout)
            logger.info(f"[browser] DOM fill: {selector} = {value[:20]}")
            return True
        except Exception as e:
            logger.warning(f"[browser] DOM fill failed: {selector} -> {e}")
            return False

    def dom_select(self, page, selector, value, timeout=5000):
        try:
            page.select_option(selector, value, timeout=timeout)
            logger.info(f"[browser] DOM select: {selector} = {value}")
            return True
        except Exception as e:
            logger.warning(f"[browser] DOM select failed: {selector} -> {e}")
            return False

    def dom_screenshot(self, page, path=None):
        try:
            data = page.screenshot(path=path)
            logger.info(f"[browser] screenshot taken")
            return data
        except Exception as e:
            logger.error(f"[browser] screenshot failed: {e}")
            return None

    def get_element_at_point(self, page, x, y):
        try:
            result = page.evaluate("""(coords) => {
                const el = document.elementFromPoint(coords.x, coords.y);
                if (!el) return null;
                const selectors = [];
                if (el.id) selectors.push('#' + CSS.escape(el.id));
                if (el.name) selectors.push(el.tagName.toLowerCase() + '[name="' + el.name + '"]');
                if (el.getAttribute('aria-label')) selectors.push(el.tagName.toLowerCase() + '[aria-label="' + el.getAttribute('aria-label') + '"]');
                if (el.getAttribute('data-testid')) selectors.push('[data-testid="' + el.getAttribute('data-testid') + '"]');
                const text = el.textContent?.trim()?.substring(0, 30);
                if (text) selectors.push(el.tagName.toLowerCase() + ':has-text("' + text + '")');
                const cls = el.className;
                if (typeof cls === 'string' && cls.trim()) {
                    const mainClass = cls.trim().split(/\\s+/)[0];
                    selectors.push(el.tagName.toLowerCase() + '.' + CSS.escape(mainClass));
                }
                selectors.push(el.tagName.toLowerCase());
                return {
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    id: el.id || '',
                    name: el.name || '',
                    text: el.textContent?.trim()?.substring(0, 100) || '',
                    href: el.href || '',
                    placeholder: el.placeholder || '',
                    selectors: selectors,
                    rect: el.getBoundingClientRect().toJSON()
                };
            }""", {"x": x, "y": y})
            return result
        except Exception as e:
            logger.warning(f"[browser] get_element_at_point failed: {e}")
            return None

    def close(self):
        for sid, ctx in self._contexts.items():
            try:
                ctx.close()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._contexts.clear()
        self._pages.clear()
        self._browser = None
        self._pw = None
        self._connected = False
        self._session_counter = 0
        logger.info("[browser] fully closed")

    def is_connected(self):
        return self._connected and self._browser is not None and self._browser.is_connected()