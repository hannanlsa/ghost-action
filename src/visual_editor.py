import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import atexit
from http.server import HTTPServer, BaseHTTPRequestHandler

from log_helpers import log_call, log_step, log_error, StepTimer

logger = logging.getLogger("visual_editor")

_HTML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
_BRIDGE_DIR = "/tmp/ga_visual_bridge"
_BRIDGE_PORT = 18432
_LOG_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "logs")


class _BridgeHandler(BaseHTTPRequestHandler):
    _callbacks = {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            action = data.get("action", "")
            payload = data.get("data", {})
            log_step("VIZ_BRIDGE", "REQUEST", f"action={action}")

            if action == "save":
                cb = self._callbacks.get("save")
                if cb:
                    result = cb(payload.get("events", []), payload.get("xml", ""))
                    self._json_response({"ok": True, "result": result})
                else:
                    self._json_response({"ok": False, "error": "no save callback"})
            elif action == "run":
                cb = self._callbacks.get("run")
                if cb:
                    result = cb(payload.get("events", []))
                    self._json_response({"ok": True, "result": result})
                else:
                    self._json_response({"ok": False, "error": "no run callback"})
            elif action == "load":
                cb = self._callbacks.get("load")
                if cb:
                    result = cb()
                    self._json_response({"ok": True, "result": result})
                else:
                    self._json_response({"ok": False, "error": "no load callback"})
            elif action == "js_error":
                log_error("VIZ_JS", "BROWSER_ERROR", f"msg={payload.get('msg')} url={payload.get('url')} line={payload.get('line')}")
                self._json_response({"ok": True})
            elif action == "js_diag":
                log_step("VIZ_JS", "DIAG", f"Drawflow={payload.get('drawflow_defined')} editor={payload.get('editor_defined')}")
                self._json_response({"ok": True})
            else:
                self._json_response({"ok": False, "error": f"unknown action: {action}"})
        except Exception as e:
            log_error("VIZ_BRIDGE", "HANDLE_ERROR", str(e))
            self._json_response({"ok": False, "error": str(e)})

    def do_GET(self):
        if self.path.startswith("/events.json") or self.path.startswith("/bridge/events.json"):
            bridge_file = os.path.join(_BRIDGE_DIR, "events.json")
            if os.path.exists(bridge_file):
                with open(bridge_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path.startswith("/thumb/"):
            fname = self.path.replace("/thumb/", "").split("?")[0]
            scripts_dir = os.path.join(os.path.expanduser("~"), "GhostAction", "scripts")
            tpl_path = os.path.join(scripts_dir, "templates", fname)
            if os.path.exists(tpl_path):
                with open(tpl_path, "rb") as f:
                    img_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "max-age=3600")
                self.end_headers()
                self.wfile.write(img_data)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass


class VisualEditor:
    def __init__(self, scripts_dir=None, on_save=None, on_load=None, on_run=None, on_record=None):
        self.scripts_dir = scripts_dir or os.path.join(os.path.expanduser("~"), "GhostAction", "scripts")
        self._on_save_cb = on_save
        self._on_load_cb = on_load
        self._on_run_cb = on_run
        self._on_record_cb = on_record
        self._process = None
        self._bridge_server = None

    @log_call("VIZ_EDITOR", "open")
    def open(self, events=None):
        try:
            import webview
            log_step("VIZ_EDITOR", "WEBVIEW_IMPORT", "pywebview imported OK")
        except ImportError:
            log_error("VIZ_EDITOR", "WEBVIEW_IMPORT_FAIL", "pywebview not installed")
            return

        html_path = os.path.join(_HTML_DIR, "visual_editor_html", "editor.html")
        blockly_path = os.path.join(_HTML_DIR, "visual_editor_html", "blockly.min.js")
        log_step("VIZ_EDITOR", "PATH_CHECK", f"html_path={html_path} exists={os.path.exists(html_path)}")
        log_step("VIZ_EDITOR", "PATH_CHECK", f"blockly_path={blockly_path} exists={os.path.exists(blockly_path)}")

        if not os.path.exists(html_path):
            log_error("VIZ_EDITOR", "HTML_NOT_FOUND", f"path={html_path}")
            return

        if not os.path.exists(blockly_path):
            log_error("VIZ_EDITOR", "BLOCKLY_NOT_FOUND", f"path={blockly_path}")
            return

        os.makedirs(_BRIDGE_DIR, exist_ok=True)
        if events:
            bridge_file = os.path.join(_BRIDGE_DIR, "events.json")
            with open(bridge_file, "w", encoding="utf-8") as f:
                json.dump({"events": events}, f, ensure_ascii=False)
            log_step("VIZ_EDITOR", "BRIDGE_WRITE", f"wrote {len(events)} events to {bridge_file}")

        thumb_dir = os.path.join(_HTML_DIR, "visual_editor_html", "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        tpl_src_dir = os.path.join(os.path.expanduser("~"), "GhostAction", "scripts", "templates")
        copied = 0
        if os.path.exists(tpl_src_dir):
            for ev in (events or []):
                tpl = ev.get("template", "") or ev.get("file", "")
                if tpl and tpl.endswith(".png"):
                    src = os.path.join(tpl_src_dir, tpl)
                    dst = os.path.join(thumb_dir, tpl)
                    if os.path.exists(src) and not os.path.exists(dst):
                        import shutil
                        shutil.copy2(src, dst)
                        copied += 1
        log_step("VIZ_EDITOR", "THUMBS_COPIED", f"copied={copied} to={thumb_dir}")

        self._start_bridge_server()

        launcher = os.path.join(_HTML_DIR, "_visual_launcher.py")
        log_dir = _LOG_DIR
        os.makedirs(log_dir, exist_ok=True)

        launcher_code = self._generate_launcher_code(html_path, log_dir)
        with open(launcher, "w", encoding="utf-8") as f:
            f.write(launcher_code)
        log_step("VIZ_EDITOR", "LAUNCHER_WRITTEN", f"path={launcher} size={len(launcher_code)}")

        cmd = [sys.executable, launcher]
        launcher_log = open(os.path.join(log_dir, "visual_launcher.log"), "w")
        self._process = subprocess.Popen(cmd, stdout=launcher_log, stderr=launcher_log, start_new_session=True)
        log_step("VIZ_EDITOR", "LAUNCHED", f"PID={self._process.pid} log={launcher_log.name} cmd={cmd}")

        atexit.register(self._kill_subprocess)
        threading.Thread(target=self._monitor_launcher, args=(self._process,), daemon=True).start()

    def _kill_subprocess(self):
        if self._process and self._process.poll() is None:
            try:
                os.kill(self._process.pid, signal.SIGTERM)
                self._process.wait(timeout=3)
                log_step("VIZ_EDITOR", "SUBPROCESS_KILLED", f"PID={self._process.pid}")
            except Exception:
                try:
                    os.kill(self._process.pid, signal.SIGKILL)
                    log_step("VIZ_EDITOR", "SUBPROCESS_FORCE_KILLED", f"PID={self._process.pid}")
                except Exception:
                    pass

    def _generate_launcher_code(self, html_path, log_dir):
        log_file = os.path.join(log_dir, "visual_launcher.log")
        return (
            "import sys, os, json, logging, time, traceback\n"
            f"LOG_FILE = {repr(log_file)}\n"
            "fh = logging.FileHandler(LOG_FILE, mode='a')\n"
            "fh.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))\n"
            "logging.getLogger().addHandler(fh)\n"
            "logging.getLogger().setLevel(logging.DEBUG)\n"
            "logger = logging.getLogger('visual_launcher')\n"
            "logger.info('=== LAUNCHER START ===')\n"
            "logger.info('Python: %s', sys.executable)\n"
            "logger.info('Version: %s', sys.version)\n"
            "logger.info('CWD: %s', os.getcwd())\n"
            "logger.info('PID: %d', os.getpid())\n"
            "logger.info('PPID: %d', os.getppid())\n"
            "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
            f"html_path = {repr(html_path)}\n"
            "logger.info('html_path=%s exists=%s', html_path, os.path.exists(html_path))\n"
            "blockly_path = os.path.join(os.path.dirname(html_path), 'blockly.min.js')\n"
            "logger.info('blockly_path=%s exists=%s size=%s', blockly_path, os.path.exists(blockly_path), os.path.getsize(blockly_path) if os.path.exists(blockly_path) else 'N/A')\n"
"try:\n"
"    import webview\n"
"    logger.info('pywebview imported OK, version=%s', getattr(webview, '__version__', 'unknown'))\n"
"except ImportError as e:\n"
"    logger.error('pywebview import FAILED: %s', e)\n"
"    sys.exit(1)\n"
"class WinApi:\n"
"    def close(self):\n"
"        webview.windows[0].destroy()\n"
"    def minimize(self):\n"
"        webview.windows[0].minimize()\n"
"    def toggle_fullscreen(self):\n"
"        w=webview.windows[0]\n"
"        w.toggle_fullscreen()\n"
"try:\n"
"    window = webview.create_window('', html_path, width=1200, height=800, min_size=(800, 600), resizable=True, js_api=WinApi())\n"
            "    logger.info('webview.create_window OK')\n"
            "except Exception as e:\n"
            "    logger.error('webview.create_window FAILED: %s', e)\n"
            "    logger.error(traceback.format_exc())\n"
            "    sys.exit(1)\n"
             "try:\n"
"    logger.info('calling webview.start()...')\n"
"    webview.start()\n"
             "    logger.info('webview.start() returned normally')\n"
            "except Exception as e:\n"
            "    logger.error('webview.start() FAILED: %s', e)\n"
            "    logger.error(traceback.format_exc())\n"
        )

    def _monitor_launcher(self, proc):
        time.sleep(3)
        rc = proc.poll()
        if rc is not None:
            log_error("VIZ_EDITOR", "LAUNCHER_EXITED", f"PID={proc.pid} exit_code={rc}")
        else:
            log_step("VIZ_EDITOR", "LAUNCHER_RUNNING", f"PID={proc.pid} still running after 3s")

    def _start_bridge_server(self):
        _BridgeHandler._callbacks = {
            "save": self._handle_save,
            "run": self._handle_run,
            "load": self._handle_load,
        }
        try:
            self._bridge_server = HTTPServer(("127.0.0.1", _BRIDGE_PORT), _BridgeHandler)
            t = threading.Thread(target=self._bridge_server.serve_forever, daemon=True)
            t.start()
            log_step("VIZ_EDITOR", "BRIDGE_STARTED", f"port={_BRIDGE_PORT}")
        except OSError as e:
            log_step("VIZ_EDITOR", "BRIDGE_PORT_IN_USE", f"port={_BRIDGE_PORT} error={e}")

    def _handle_save(self, events, blockly_xml=""):
        log_step("VIZ_EDITOR", "SAVE", f"events={len(events)}")
        if self._on_save_cb:
            return self._on_save_cb(events, blockly_xml)
        os.makedirs(self.scripts_dir, exist_ok=True)
        script_name = f"visual_{int(time.time())}"
        script_data = {
            "name": script_name,
            "events": events,
            "blockly_xml": blockly_xml,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "visual_editor",
        }
        script_path = os.path.join(self.scripts_dir, f"{script_name}.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        log_step("VIZ_EDITOR", "SAVE_DONE", f"name={script_name} events={len(events)}")
        return {"ok": True, "name": script_name, "path": script_path}

    def _handle_run(self, events):
        log_step("VIZ_EDITOR", "RUN", f"events={len(events)}")
        if self._on_run_cb:
            return self._on_run_cb(events)
        return {"ok": True}

    def _handle_load(self):
        log_step("VIZ_EDITOR", "LOAD", "")
        bridge_file = os.path.join(_BRIDGE_DIR, "events.json")
        if os.path.exists(bridge_file):
            try:
                with open(bridge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                events = data.get("events", [])
                if events:
                    log_step("VIZ_EDITOR", "LOAD_BRIDGE", f"loaded {len(events)} events from bridge file")
                    return {"events": events, "xml": ""}
            except Exception as e:
                log_error("VIZ_EDITOR", "LOAD_BRIDGE_FAIL", str(e))
        if self._on_load_cb:
            return self._on_load_cb()
        scripts = []
        if os.path.exists(self.scripts_dir):
            for fname in os.listdir(self.scripts_dir):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(self.scripts_dir, fname), "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if data.get("events"):
                            scripts.append(data)
                    except Exception:
                        pass
        if scripts:
            return {"events": scripts[-1].get("events", []), "xml": scripts[-1].get("blockly_xml", "")}
        return {"events": [], "xml": ""}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    editor = VisualEditor()
    editor.open()
    time.sleep(30)
