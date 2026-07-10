import json
import os
import time
import re


_USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "GhostAction")
SCRIPTS_DIR = os.path.join(_USER_DATA_DIR, "scripts")


class ScriptManager:
    def __init__(self, scripts_dir=None):
        self.scripts_dir = scripts_dir or SCRIPTS_DIR
        os.makedirs(self.scripts_dir, exist_ok=True)

    def save(self, name, events, meta=None, intent="", skill_meta=None):
        script = {
            "name": name,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_count": len(events),
            "meta": meta or {},
            "intent": intent or "",
            "skill_meta": skill_meta or {},
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
                    sm = data.get("skill_meta", {})
                    result.append({
                        "name": data.get("name", fname[:-5]),
                        "events": data.get("event_count", 0),
                        "created": data.get("created", ""),
                        "intent": data.get("intent", ""),
                        "triggers": sm.get("triggers", []),
                        "category": sm.get("category", ""),
                        "tags": sm.get("tags", []),
                        "params": sm.get("params", []),
                    })
                except Exception:
                    result.append({"name": fname[:-5], "events": 0, "created": "",
                                   "intent": "", "triggers": [], "category": "", "tags": [], "params": []})
        return result

    def delete(self, name):
        path = os.path.join(self.scripts_dir, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def search(self, query):
        query_lower = query.lower().strip()
        if not query_lower:
            return self.list_all()
        results = []
        for s in self.list_all():
            score = 0
            if query_lower in s.get("name", "").lower():
                score += 10
            if query_lower in s.get("intent", "").lower():
                score += 8
            for t in s.get("triggers", []):
                if query_lower in t.lower():
                    score += 6
                elif t.lower() in query_lower:
                    score += 4
            for tag in s.get("tags", []):
                if query_lower in tag.lower():
                    score += 5
            if query_lower in s.get("category", "").lower():
                score += 3
            if score > 0:
                results.append((score, s))
        results.sort(key=lambda x: -x[0])
        return [s for _, s in results]

    def auto_generate_skill_meta(self, events, meta, intent=""):
        pid_names = meta.get("pid_names", {})
        windows = set(pid_names.values())
        actions = set()
        for e in events:
            etype = e.get("type", "")
            if etype == "mouse_down":
                ax = e.get("ax_element", {})
                if ax.get("AXTitle"):
                    actions.add(ax["AXTitle"])
                anchor = e.get("ocr_anchor", {})
                if anchor.get("text"):
                    actions.add(anchor["text"])
            elif etype == "key_down":
                text = e.get("text", "")
                if text and len(text) > 1:
                    actions.add(text)

        triggers = []
        for w in windows:
            if w:
                triggers.append(w)
        for a in list(actions)[:3]:
            if a and len(a) <= 10:
                triggers.append(a)

        tags = []
        for w in windows:
            if w:
                tags.append(w)

        category = ""
        if any(w in "".join(windows) for w in ["微信", "QQ", "钉钉", "飞书", "Telegram"]):
            category = "通讯"
        elif any(w in "".join(windows) for w in ["Chrome", "Safari", "Firefox", "Edge"]):
            category = "浏览器"
        elif any(w in "".join(windows) for w in ["Excel", "Word", "PPT", "Numbers", "Pages"]):
            category = "办公"
        elif any(w in "".join(windows) for w in ["Finder", "资源管理器"]):
            category = "文件管理"

        params = []
        for e in events:
            if e.get("type") == "type_text" or (e.get("type") == "key_down" and e.get("text", "")):
                text = e.get("text", "")
                if text and len(text) > 1 and not text.startswith("http"):
                    var_name = re.sub(r'[^\w]', '_', text[:8]).strip('_') or "input"
                    if not any(p["name"] == var_name for p in params):
                        params.append({"name": var_name, "type": "string", "required": False, "desc": f"输入内容(默认:{text})"})

        return {
            "triggers": triggers[:5],
            "params": params[:5],
            "assertions": [],
            "category": category,
            "tags": list(set(tags))[:5],
        }
