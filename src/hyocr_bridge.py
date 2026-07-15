import base64
import io
import json
import logging
import os
import subprocess
import time
import threading

import mss
from PIL import Image

from log_helpers import action_log, sync_log, log_call, StepTimer

logger = logging.getLogger("action")

LLAMA_SERVER_BIN = os.environ.get(
    "HYOCR_LLAMA_SERVER",
    "/Users/panxiao/llama.cpp/build/bin/llama-server",
)
MODEL_PATH = os.environ.get(
    "HYOCR_MODEL_PATH",
    "/Users/panxiao/HunyuanOCR/hyocr-q4_k_m.gguf",
)
MMPROJ_PATH = os.environ.get(
    "HYOCR_MMPROJ_PATH",
    "/Users/panxiao/HunyuanOCR/mmproj-hyocr-q4_k_m.gguf",
)
HYOCR_PORT = int(os.environ.get("HYOCR_PORT", "18433"))
HYOCR_HOST = os.environ.get("HYOCR_HOST", "127.0.0.1")
HYOCR_CTX_SIZE = int(os.environ.get("HYOCR_CTX_SIZE", "8192"))
HYOCR_N_PREDICT = int(os.environ.get("HYOCR_N_PREDICT", "4096"))

_server_proc = None
_server_lock = threading.Lock()
_server_ready = False


def _is_server_running():
    import urllib.request
    try:
        url = f"http://{HYOCR_HOST}:{HYOCR_PORT}/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


@log_call("HYOCR", "START_SERVER")
def start_server(timeout=60):
    global _server_proc, _server_ready
    with _server_lock:
        if _is_server_running():
            _server_ready = True
            logger.info("[HYOCR] server already running on port %d", HYOCR_PORT)
            return True

        if not os.path.isfile(MODEL_PATH):
            logger.error("[HYOCR] model not found: %s", MODEL_PATH)
            return False

        mmproj_args = []
        if os.path.isfile(MMPROJ_PATH):
            mmproj_args = ["--mmproj", MMPROJ_PATH]

        cmd = [
            LLAMA_SERVER_BIN,
            "--model", MODEL_PATH,
            *mmproj_args,
            "--host", HYOCR_HOST,
            "--port", str(HYOCR_PORT),
            "--ctx-size", str(HYOCR_CTX_SIZE),
            "--n-predict", str(HYOCR_N_PREDICT),
            "--threads", str(min(os.cpu_count() or 4, 4)),
        ]

        logger.info("[HYOCR] starting server: %s", " ".join(cmd))
        log_dir = os.path.expanduser("~/GhostAction/logs")
        os.makedirs(log_dir, exist_ok=True)

        _server_proc = subprocess.Popen(
            cmd,
            stdout=open(os.path.join(log_dir, "hyocr_server.log"), "w"),
            stderr=subprocess.STDOUT,
        )

        t0 = time.time()
        while time.time() - t0 < timeout:
            if _server_proc.poll() is not None:
                logger.error("[HYOCR] server exited with code %d", _server_proc.returncode)
                return False
            if _is_server_running():
                _server_ready = True
                elapsed = (time.time() - t0) * 1000
                logger.info("[HYOCR] server ready in %.0fms", elapsed)
                return True
            time.sleep(1)

        logger.error("[HYOCR] server startup timed out after %ds", timeout)
        return False


@log_call("HYOCR", "STOP_SERVER")
def stop_server():
    global _server_proc, _server_ready
    with _server_lock:
        if _server_proc and _server_proc.poll() is None:
            _server_proc.terminate()
            try:
                _server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _server_proc.kill()
            logger.info("[HYOCR] server stopped")
        _server_proc = None
        _server_ready = False


def _screenshot_to_base64(x, y, region_size=200):
    half = region_size // 2
    region = {
        "left": max(0, int(x) - half),
        "top": max(0, int(y) - half),
        "width": region_size,
        "height": region_size,
    }
    with mss.MSS() as sct:
        screenshot = sct.grab(region)
    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@log_call("HYOCR", "RECOGNIZE")
def recognize(x, y, region_size=200, task="ocr"):
    if not _server_ready and not _is_server_running():
        if not start_server():
            return []

    b64_img = _screenshot_to_base64(x, y, region_size)
    data_url = f"data:image/png;base64,{b64_img}"

    prompt = "OCR"
    if task == "doc_parse":
        prompt = "Parse the document"
    elif task == "text_spot":
        prompt = "Recognize all text in the image"

    payload = {
        "model": "HYVL",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.0,
    }

    import urllib.request
    url = f"http://{HYOCR_HOST}:{HYOCR_PORT}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        logger.error("[HYOCR] RECOGNIZE_FAIL elapsed=%.0fms error=%s", elapsed, e)
        return []

    elapsed = (time.time() - t0) * 1000

    text = ""
    try:
        text = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        pass

    if not text:
        logger.debug("[HYOCR] RECOGNIZE_DONE elapsed=%.0fms text=(empty)", elapsed)
        return []

    logger.info("[HYOCR] RECOGNIZE_DONE elapsed=%.0fms text=%s", elapsed, text[:100])

    half = region_size // 2
    results = []
    lines = text.strip().split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        offset_y = i * 20 - half
        results.append({
            "text": line,
            "x": x,
            "y": y + offset_y,
            "offset_x": 0,
            "offset_y": offset_y,
            "source": "hyocr",
        })

    return results


@log_call("HYOCR", "RECOGNIZE_FULL")
def recognize_full(image_path=None, task="ocr"):
    if not _server_ready and not _is_server_running():
        if not start_server():
            return ""

    if image_path and os.path.isfile(image_path):
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"
    else:
        return ""

    prompt = "OCR"
    if task == "doc_parse":
        prompt = "Parse the document"

    payload = {
        "model": "HYVL",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.0,
    }

    import urllib.request
    url = f"http://{HYOCR_HOST}:{HYOCR_PORT}/v1/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        logger.error("[HYOCR] RECOGNIZE_FULL_FAIL elapsed=%.0fms error=%s", elapsed, e)
        return ""

    elapsed = (time.time() - t0) * 1000

    text = ""
    try:
        text = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        pass

    logger.info("[HYOCR] RECOGNIZE_FULL_DONE elapsed=%.0fms len=%d", elapsed, len(text))
    return text


def is_available():
    return os.path.isfile(MODEL_PATH) and os.path.isfile(LLAMA_SERVER_BIN)