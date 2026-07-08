import os
import json
import logging
import requests

APP_REPO = "hannanlsa/ghost-action"
CURRENT_VERSION = "1.3.0"

logger = logging.getLogger("marketplace")

MARKETPLACE_REPO = "hannanlsa/ghost-action-marketplace"
GITHUB_API = "https://api.github.com"

_marketplace_token = ""


def set_token(token):
    global _marketplace_token
    _marketplace_token = token


def _headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if _marketplace_token:
        h["Authorization"] = f"token {_marketplace_token}"
    return h


def get_index():
    try:
        url = f"{GITHUB_API}/repos/{MARKETPLACE_REPO}/contents/index.json"
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code == 200:
            import base64
            content = resp.json()["content"]
            return json.loads(base64.b64decode(content).decode("utf-8"))
        logger.warning("获取市场索引失败: %d", resp.status_code)
        return None
    except Exception as e:
        logger.error("获取市场索引异常: %s", e)
        return None


def search_scripts(keyword=""):
    index = get_index()
    if not index:
        return []
    keyword = keyword.lower()
    results = []
    for s in index.get("scripts", []):
        if not keyword:
            results.append(s)
            continue
        searchable = f"{s.get('name','')} {s.get('description','')} {s.get('target_app','')} {' '.join(s.get('tags',[]))} {s.get('author','')}".lower()
        if keyword in searchable:
            results.append(s)
    return results


def download_script(script_entry):
    try:
        path = script_entry.get("path", "")
        if not path:
            return None
        url = f"{GITHUB_API}/repos/{MARKETPLACE_REPO}/contents/{path}"
        resp = requests.get(url, headers=_headers(), timeout=15)
        if resp.status_code == 200:
            import base64
            content = resp.json()["content"]
            return json.loads(base64.b64decode(content).decode("utf-8"))
        logger.warning("下载脚本失败: %d", resp.status_code)
        return None
    except Exception as e:
        logger.error("下载脚本异常: %s", e)
        return None


def upload_script(script_data, token=None):
    if token:
        set_token(token)
    if not _marketplace_token:
        logger.error("未设置GitHub Token，无法上传")
        return None
    try:
        name = script_data.get("name", "unnamed")
        description = f"GhostAction Script: {name}"
        tags = script_data.get("meta", {}).get("tags", [])
        if tags:
            description += f" [{','.join(tags)}]"

        url = f"{GITHUB_API}/gists"
        payload = {
            "description": description,
            "public": True,
            "files": {
                "script.json": {
                    "content": json.dumps(script_data, ensure_ascii=False, indent=2)
                }
            }
        }
        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        if resp.status_code == 201:
            gist = resp.json()
            gist_url = gist["html_url"]
            gist_id = gist["id"]
            logger.info("脚本已上传到Gist: %s", gist_url)
            return {"gist_id": gist_id, "gist_url": gist_url}
        logger.error("上传Gist失败: %d %s", resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("上传脚本异常: %s", e)
        return None


def compute_fingerprint(script_data):
    events = script_data.get("events", [])
    meta = script_data.get("meta", {})
    pids = set(e.get("pid") for e in events if e.get("pid"))
    ocr_count = sum(1 for e in events if e.get("ocr_anchor"))
    tpl_count = sum(1 for e in events if e.get("template"))
    total = max(len(events), 1)
    return {
        "step_count": len(events),
        "window_count": len(pids),
        "ocr_coverage": round(ocr_count / total, 2),
        "template_coverage": round(tpl_count / total, 2),
        "has_logic_chain": bool(meta.get("logic_chain")),
        "duration": events[-1].get("time", 0) - events[0].get("time", 0) if len(events) >= 2 else 0,
    }


def compare_fingerprints(local_fp, remote_fp):
    score = 0
    if remote_fp.get("step_count", 0) > local_fp.get("step_count", 0):
        score += 1
    if remote_fp.get("ocr_coverage", 0) > local_fp.get("ocr_coverage", 0):
        score += 1
    if remote_fp.get("template_coverage", 0) > local_fp.get("template_coverage", 0):
        score += 1
    if remote_fp.get("has_logic_chain") and not local_fp.get("has_logic_chain"):
        score += 1
    if remote_fp.get("window_count", 0) > local_fp.get("window_count", 0):
        score += 1
    return score


def merge_scripts(local_data, remote_data):
    local_events = list(local_data.get("events", []))
    remote_events = remote_data.get("events", [])

    merged = list(local_events)
    added = 0
    enhanced = 0

    for r_event in remote_events:
        r_type = r_event.get("type", "")
        if r_type in ("mouse_up", "key_up"):
            continue

        is_dup = False
        for i, l_event in enumerate(merged):
            l_type = l_event.get("type", "")
            if l_type != r_type:
                continue
            if l_type == "mouse_down":
                if abs(l_event.get("x", 0) - r_event.get("x", 0)) < 10 and abs(l_event.get("y", 0) - r_event.get("y", 0)) < 10:
                    if r_event.get("ocr_anchor") and not l_event.get("ocr_anchor"):
                        merged[i]["ocr_anchor"] = r_event["ocr_anchor"]
                        enhanced += 1
                    if r_event.get("template") and not l_event.get("template"):
                        merged[i]["template"] = r_event["template"]
                        enhanced += 1
                    if r_event.get("ax_element") and not l_event.get("ax_element"):
                        merged[i]["ax_element"] = r_event["ax_element"]
                        enhanced += 1
                    is_dup = True
                    break
            elif l_type == "key_down":
                if l_event.get("keycode") == r_event.get("keycode"):
                    is_dup = True
                    break
            elif l_type == "scroll":
                if abs(l_event.get("dy", 0) - r_event.get("dy", 0)) < 5:
                    is_dup = True
                    break

        if not is_dup:
            merged.append(r_event)
            added += 1

    result = dict(local_data)
    result["events"] = merged
    if "meta" not in result:
        result["meta"] = {}
    result["meta"]["merged_from"] = remote_data.get("name", "unknown")
    result["meta"]["merge_info"] = {"added": added, "enhanced": enhanced}
    return result, added, enhanced


def check_update():
    try:
        url = f"{GITHUB_API}/repos/{APP_REPO}/releases/latest"
        resp = requests.get(url, headers=_headers(), timeout=10)
        if resp.status_code != 200:
            return None
        release = resp.json()
        tag = release.get("tag_name", "").lstrip("v")
        if not tag:
            return None
        if _compare_versions(tag, CURRENT_VERSION) > 0:
            return {
                "version": tag,
                "url": release.get("html_url", ""),
                "notes": release.get("body", ""),
                "download_url": "",
            }
            for asset in release.get("assets", []):
                if asset.get("name", "").endswith(".dmg"):
                    result["download_url"] = asset["browser_download_url"]
                    break
            return result
        return None
    except Exception as e:
        logger.debug("检查更新失败: %s", e)
        return None


def _compare_versions(v1, v2):
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    for a, b in zip(parts1, parts2):
        if a != b:
            return a - b
    return len(parts1) - len(parts2)