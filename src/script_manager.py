import json
import os
import time


_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "GhostAction")
SCRIPTS_DIR = os.path.join(_USER_DATA_DIR, "scripts")


class ScriptManager:
    def __init__(self, scripts_dir=None):
        self.scripts_dir = scripts_dir or SCRIPTS_DIR
        os.makedirs(self.scripts_dir, exist_ok=True)

    def save(self, name, events, meta=None):
        script = {
            "name": name,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_count": len(events),
            "meta": meta or {},
            "events": events,
        }
        path = os.path.join(self.scripts_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        return path

    def load(self, name):
        path = os.path.join(self.scripts_dir, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_all(self):
        result = []
        if not os.path.exists(self.scripts_dir):
            return result
        for fname in sorted(os.listdir(self.scripts_dir)):
            if fname.endswith(".json"):
                path = os.path.join(self.scripts_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    result.append({
                        "name": data.get("name", fname[:-5]),
                        "events": data.get("event_count", 0),
                        "created": data.get("created", ""),
                    })
                except Exception:
                    result.append({"name": fname[:-5], "events": 0, "created": ""})
        return result

    def delete(self, name):
        path = os.path.join(self.scripts_dir, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False