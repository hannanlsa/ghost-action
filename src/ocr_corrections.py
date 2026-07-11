import os
import json
import hashlib
import logging

logger = logging.getLogger("ocr_corrections")

CORRECTIONS_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "ocr_corrections")
CORRECTIONS_FILE = os.path.join(CORRECTIONS_DIR, "corrections.json")


def _ensure_dir():
    os.makedirs(CORRECTIONS_DIR, exist_ok=True)


def _image_hash(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_corrections():
    _ensure_dir()
    if os.path.exists(CORRECTIONS_FILE):
        try:
            with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"entries": {}}


def save_corrections(data):
    _ensure_dir()
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def lookup_correction(image_path):
    if not image_path or not os.path.exists(image_path):
        return None
    h = _image_hash(image_path)
    if not h:
        return None
    data = load_corrections()
    entry = data.get("entries", {}).get(h)
    if entry:
        return entry.get("corrected_text") or entry.get("original_text")
    return None


def record_correction(image_path, original_text, corrected_text, source="manual"):
    if not image_path or not os.path.exists(image_path):
        return
    h = _image_hash(image_path)
    if not h:
        return
    data = load_corrections()
    if "entries" not in data:
        data["entries"] = {}
    if original_text == corrected_text:
        data["entries"][h] = {
            "original_text": original_text,
            "corrected_text": corrected_text,
            "verified": True,
            "source": source,
            "image_path": image_path,
        }
    else:
        data["entries"][h] = {
            "original_text": original_text,
            "corrected_text": corrected_text,
            "verified": False,
            "source": source,
            "image_path": image_path,
        }
    save_corrections(data)
    logger.info("OCR修正记录: '%s' -> '%s' (hash=%s)", original_text, corrected_text, h[:8])


def get_correction_stats():
    data = load_corrections()
    entries = data.get("entries", {})
    total = len(entries)
    verified = sum(1 for e in entries.values() if e.get("verified"))
    corrected = sum(1 for e in entries.values() if not e.get("verified") and e.get("corrected_text") != e.get("original_text"))
    return {"total": total, "verified": verified, "corrected": corrected}