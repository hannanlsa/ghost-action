import json
import logging
import os
import sys
import threading
import time

from log_helpers import log_call, log_step, log_error, StepTimer
logger = logging.getLogger("visual_editor")

_HTML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visual_editor_html")


class VisualEditorAPI:
    def __init__(self, editor):
        self._editor = editor

    def save_script(self, events_json, blockly_xml=""):
        try:
            events = json.loads(events_json)
            return self._editor._on_save(events, blockly_xml)
        except Exception as e:
            logger.error("save_script error: %s", e)
            return json.dumps({"ok": False, "error": str(e)})

    def load_script(self):
        try:
            return self._editor._on_load()
        except Exception as e:
            logger.error("load_script error: %s", e)
            return json.dumps({"ok": False, "error": str(e)})

    def run_script(self, events_json):
        try:
            events = json.loads(events_json)
            return self._editor._on_run(events)
        except Exception as e:
            logger.error("run_script error: %s", e)
            return json.dumps({"ok": False, "error": str(e)})

    def record_script(self):
        try:
            return self._editor._on_record()
        except Exception as e:
            logger.error("record_script error: %s", e)
            return json.dumps({"ok": False, "error": str(e)})


class VisualEditor:
    def __init__(self, scripts_dir=None, on_save=None, on_load=None, on_run=None, on_record=None):
        self.scripts_dir = scripts_dir or os.path.join(os.path.expanduser("~"), "GhostAction", "scripts")
        self._on_save_cb = on_save
        self._on_load_cb = on_load
        self._on_run_cb = on_run
        self._on_record_cb = on_record
        self._window = None
        self._api = VisualEditorAPI(self)
        self._events_to_load = None

    @log_call("VIZ_EDITOR", "open")
    def open(self, events=None):
        try:
            import webview
        except ImportError:
            logger.error("pywebview not installed. Install: pip install pywebview")
            return

        html_path = os.path.join(_HTML_DIR, "editor.html")
        if not os.path.exists(html_path):
            logger.error("editor.html not found at %s", html_path)
            return

        self._events_to_load = events

        self._window = webview.create_window(
            "GhostAction Visual Editor",
            html_path,
            js_api=self._api,
            width=1200,
            height=800,
            min_size=(800, 600),
            resizable=True,
        )

        def on_loaded():
            if self._events_to_load:
                events_json = json.dumps(self._events_to_load)
                escaped = events_json.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                self._window.evaluate_js(f"loadEventsFromPython('{escaped}')")

        self._window.events.loaded += on_loaded

        import subprocess
        bridge_path = os.path.join(_HTML_DIR, "..", "_visual_bridge.json")
        if events:
            with open(bridge_path, "w", encoding="utf-8") as f:
                json.dump({"events": events}, f, ensure_ascii=False)

        launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_launcher.py")
        with open(launcher, "w", encoding="utf-8") as f:
            f.write("import sys, os, json, logging\n")
            f.write("sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n")
            f.write("logging.basicConfig(level=logging.INFO)\n")
            f.write("import webview\n")
            f.write("from visual_editor import VisualEditor, VisualEditorAPI\n")
            f.write(f"scripts_dir = {repr(self.scripts_dir)}\n")
            f.write("editor = VisualEditor(scripts_dir=scripts_dir)\n")
            f.write("api = VisualEditorAPI(editor)\n")
            f.write("bridge_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'visual_editor_html', '..', '_visual_bridge.json')\n")
            f.write("events = None\n")
            f.write("if os.path.exists(bridge_path):\n")
            f.write("    try:\n")
            f.write("        with open(bridge_path, 'r', encoding='utf-8') as bf:\n")
            f.write("            bd = json.load(bf)\n")
            f.write("            events = bd.get('events')\n")
            f.write("    except Exception:\n")
            f.write("        pass\n")
            f.write("window = webview.create_window('GhostAction Visual Editor', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'visual_editor_html', 'editor.html'), js_api=api, width=1200, height=800, min_size=(800, 600), resizable=True)\n")
            f.write("def on_loaded():\n")
            f.write("    if events:\n")
            f.write("        ej = json.dumps(events)\n")
            f.write("        escaped = ej.replace('\\\\', '\\\\\\\\').replace(\"'\", \"\\\\'\").replace('\\n', '\\\\n')\n")
            f.write("        window.evaluate_js(f\"loadEventsFromPython('{escaped}')\")\n")
            f.write("window.events.loaded += on_loaded\n")
            f.write("webview.start(debug=False)\n")

        cmd = [sys.executable, launcher]
        self._process = subprocess.Popen(cmd, start_new_session=True)
        logger.info("Visual Editor launched as subprocess PID=%d", self._process.pid)


    @log_call("VIZ_EDITOR", "_on_save")
    def _on_save(self, events, blockly_xml=""):
        if self._on_save_cb:
            result = self._on_save_cb(events, blockly_xml)
            return json.dumps({"ok": True, "result": result})

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
        logger.info("Saved visual script: %s (%d events)", script_name, len(events))
        return json.dumps({"ok": True, "name": script_name, "path": script_path})

    @log_call("VIZ_EDITOR", "_on_load")
    def _on_load(self):
        if self._on_load_cb:
            return self._on_load_cb()

        scripts = []
        if os.path.exists(self.scripts_dir):
            for fname in os.listdir(self.scripts_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.scripts_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if data.get("events"):
                            scripts.append(data)
                    except Exception:
                        pass
        if scripts:
            return json.dumps({"events": scripts[-1].get("events", []), "xml": scripts[-1].get("blockly_xml", "")})
        return json.dumps({"events": [], "xml": ""})

    @log_call("VIZ_EDITOR", "_on_run")
    def _on_run(self, events):
        if self._on_run_cb:
            result = self._on_run_cb(events)
            return json.dumps({"ok": True, "result": result})
        logger.info("Run script: %d events (no callback, logging only)", len(events))
        return json.dumps({"ok": True, "message": "No run callback registered"})

    @log_call("VIZ_EDITOR", "_on_record")
    def _on_record(self):
        if self._on_record_cb:
            return self._on_record_cb()
        return json.dumps({"ok": False, "error": "No record callback registered"})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    editor = VisualEditor()
    editor.open()
    time.sleep(30)