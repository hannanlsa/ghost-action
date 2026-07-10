import os
import json
import logging
import base64
import time
import socket

logger = logging.getLogger("ai_recognizer")

CONFIG_PATH = os.path.join(os.path.expanduser("~"), "GhostAction", "ai_config.json")
LOCAL_MODEL_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "models")

MODEL_REGISTRY = {
    # === 智谱 (ZhipuAI) ===
    "glm-4v-flash": {
        "name": "GLM-4V Flash",
        "provider": "zhipu",
        "capabilities": ["vision", "text"],
        "free": True,
        "model_id": "glm-4v-flash",
        "description": "智谱免费视觉模型，擅长验证码/图表识别（默认图形识别）",
    },
    "glm-4v-plus": {
        "name": "GLM-4V Plus",
        "provider": "zhipu",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "glm-4v-plus",
        "description": "智谱付费视觉模型，更强识别能力",
    },
    "glm-4v": {
        "name": "GLM-4V",
        "provider": "zhipu",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "glm-4v",
        "description": "智谱旗舰视觉模型",
    },
    "glm-4-flash": {
        "name": "GLM-4 Flash",
        "provider": "zhipu",
        "capabilities": ["text"],
        "free": True,
        "model_id": "glm-4-flash",
        "description": "智谱免费文本模型",
    },
    "glm-4-plus": {
        "name": "GLM-4 Plus",
        "provider": "zhipu",
        "capabilities": ["text"],
        "free": False,
        "model_id": "glm-4-plus",
        "description": "智谱付费文本模型",
    },
    # === DeepSeek ===
    "deepseek-chat": {
        "name": "DeepSeek Chat",
        "provider": "deepseek",
        "capabilities": ["text"],
        "free": True,
        "model_id": "deepseek-chat",
        "description": "DeepSeek免费文本模型，擅长逻辑推理（默认文本）",
    },
    "deepseek-reasoner": {
        "name": "DeepSeek Reasoner",
        "provider": "deepseek",
        "capabilities": ["text"],
        "free": False,
        "model_id": "deepseek-reasoner",
        "description": "DeepSeek付费推理模型(R1)",
    },
    "deepseek-chat-pro": {
        "name": "DeepSeek Chat Pro",
        "provider": "deepseek",
        "capabilities": ["text"],
        "free": False,
        "model_id": "deepseek-chat",
        "description": "DeepSeek Pro版文本模型",
    },
    # === 通义千问 (Qwen/DashScope) ===
    "qwen-vl-plus": {
        "name": "Qwen-VL Plus",
        "provider": "dashscope",
        "capabilities": ["vision", "text"],
        "free": True,
        "model_id": "qwen-vl-plus",
        "description": "通义千问免费视觉模型",
    },
    "qwen-vl-max": {
        "name": "Qwen-VL Max",
        "provider": "dashscope",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "qwen-vl-max",
        "description": "通义千问旗舰视觉模型",
    },
    "qwen-turbo": {
        "name": "Qwen Turbo",
        "provider": "dashscope",
        "capabilities": ["text"],
        "free": True,
        "model_id": "qwen-turbo",
        "description": "通义千问免费文本模型",
    },
    "qwen-plus": {
        "name": "Qwen Plus",
        "provider": "dashscope",
        "capabilities": ["text"],
        "free": False,
        "model_id": "qwen-plus",
        "description": "通义千问付费文本模型",
    },
    "qwen-max": {
        "name": "Qwen Max",
        "provider": "dashscope",
        "capabilities": ["text"],
        "free": False,
        "model_id": "qwen-max",
        "description": "通义千问旗舰文本模型",
    },
    # === 百度文心 (ERNIE/Baidu) ===
    "ernie-4.0-8k": {
        "name": "ERNIE 4.0 8K",
        "provider": "baidu",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "ernie-4.0-8k",
        "description": "百度文心4.0旗舰模型",
    },
    "ernie-3.5-8k": {
        "name": "ERNIE 3.5 8K",
        "provider": "baidu",
        "capabilities": ["text"],
        "free": True,
        "model_id": "ernie-3.5-8k",
        "description": "百度文心3.5免费模型",
    },
    "ernie-speed-8k": {
        "name": "ERNIE Speed 8K",
        "provider": "baidu",
        "capabilities": ["text"],
        "free": True,
        "model_id": "ernie-speed-8k",
        "description": "百度文心Speed免费模型",
    },
    # === 月之暗面 (Moonshot/Kimi) ===
    "moonshot-v1-8k": {
        "name": "Moonshot V1 8K",
        "provider": "moonshot",
        "capabilities": ["text"],
        "free": True,
        "model_id": "moonshot-v1-8k",
        "description": "Kimi免费文本模型",
    },
    "moonshot-v1-32k": {
        "name": "Moonshot V1 32K",
        "provider": "moonshot",
        "capabilities": ["text"],
        "free": False,
        "model_id": "moonshot-v1-32k",
        "description": "Kimi付费长文本模型",
    },
    # === 讯飞星火 (Spark) ===
    "spark-lite": {
        "name": "Spark Lite",
        "provider": "spark",
        "capabilities": ["text"],
        "free": True,
        "model_id": "spark-lite",
        "description": "讯飞星火免费模型",
    },
    "spark-pro": {
        "name": "Spark Pro",
        "provider": "spark",
        "capabilities": ["text"],
        "free": False,
        "model_id": "spark-pro",
        "description": "讯飞星火Pro模型",
    },
    "spark-max": {
        "name": "Spark Max",
        "provider": "spark",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "spark-max",
        "description": "讯飞星火旗舰视觉模型",
    },
    # === OpenAI ===
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "provider": "openai",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "gpt-4o-mini",
        "description": "OpenAI轻量视觉模型",
    },
    "gpt-4o": {
        "name": "GPT-4o",
        "provider": "openai",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "gpt-4o",
        "description": "OpenAI旗舰视觉模型",
    },
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "provider": "openai",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "gpt-4-turbo",
        "description": "OpenAI GPT-4 Turbo视觉模型",
    },
    "o1-mini": {
        "name": "o1-mini",
        "provider": "openai",
        "capabilities": ["text"],
        "free": False,
        "model_id": "o1-mini",
        "description": "OpenAI推理模型",
    },
    # === Google Gemini ===
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "provider": "google",
        "capabilities": ["vision", "text"],
        "free": True,
        "model_id": "gemini-2.0-flash",
        "description": "Google免费视觉模型",
    },
    "gemini-2.0-pro": {
        "name": "Gemini 2.0 Pro",
        "provider": "google",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "gemini-2.0-pro",
        "description": "Google旗舰视觉模型",
    },
    # === Claude (Anthropic) ===
    "claude-3.5-sonnet": {
        "name": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "claude-3-5-sonnet-20241022",
        "description": "Anthropic旗舰视觉模型",
    },
    "claude-3-haiku": {
        "name": "Claude 3 Haiku",
        "provider": "anthropic",
        "capabilities": ["vision", "text"],
        "free": False,
        "model_id": "claude-3-haiku-20240307",
        "description": "Anthropic轻量视觉模型",
    },
}

PROVIDER_CONFIG = {
    "zhipu": {
        "name": "智谱 (GLM)",
        "api_base": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "signup_url": "https://open.bigmodel.cn/",
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_base": "https://api.deepseek.com/chat/completions",
        "signup_url": "https://platform.deepseek.com/",
    },
    "dashscope": {
        "name": "通义千问 (Qwen)",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "signup_url": "https://dashscope.console.aliyun.com/",
    },
    "baidu": {
        "name": "百度文心 (ERNIE)",
        "api_base": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
        "signup_url": "https://console.bce.baidu.com/qianfan/",
    },
    "moonshot": {
        "name": "月之暗面 (Kimi)",
        "api_base": "https://api.moonshot.cn/v1/chat/completions",
        "signup_url": "https://platform.moonshot.cn/",
    },
    "spark": {
        "name": "讯飞星火 (Spark)",
        "api_base": "https://spark-api-open.xf-yun.com/v1/chat/completions",
        "signup_url": "https://xinghuo.xfyun.cn/",
    },
    "openai": {
        "name": "OpenAI",
        "api_base": "https://api.openai.com/v1/chat/completions",
        "signup_url": "https://platform.openai.com/",
    },
    "google": {
        "name": "Google Gemini",
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "signup_url": "https://aistudio.google.com/",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "api_base": "https://api.anthropic.com/v1/messages",
        "signup_url": "https://console.anthropic.com/",
    },
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    default_providers = {}
    for key, info in PROVIDER_CONFIG.items():
        default_providers[key] = {"api_key": "", "enabled": True}
    return {
        "providers": default_providers,
        "vision_model": "glm-4v-flash",
        "text_model": "deepseek-chat",
        "fallback_to_manual": True,
    }


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _get_api_key(config, provider):
    return config.get("providers", {}).get(provider, {}).get("api_key", "")


def _encode_image_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _screenshot_region(x, y, w, h, save_path=None):
    import mss
    from PIL import Image
    region = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
    with mss.MSS() as sct:
        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        img.save(save_path)
    return img


def _call_openai_compatible(api_base, api_key, model_id, messages):
    import requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.1,
    }
    resp = requests.post(api_base, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_anthropic(api_key, model_id, messages):
    import requests
    system_text = ""
    user_content = []
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                user_content.append({"type": "text", "text": msg["content"]})
            elif isinstance(msg["content"], list):
                for part in msg["content"]:
                    user_content.append(part)
        elif msg["role"] == "system":
            system_text = msg["content"]
    payload = {
        "model": model_id,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system_text:
        payload["system"] = system_text
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def _call_baidu(api_key, model_id, messages):
    import requests
    headers = {"Content-Type": "application/json"}
    content_parts = []
    for msg in messages:
        if isinstance(msg.get("content"), str):
            content_parts.append(msg["content"])
        elif isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if part.get("type") == "text":
                    content_parts.append(part["text"])
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": " ".join(content_parts)}],
    }
    resp = requests.post(
        "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
        params={"access_token": api_key},
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", data.get("choices", [{}])[0].get("message", {}).get("content", ""))


def _dispatch_call(provider, api_key, model_id, messages):
    pconfig = PROVIDER_CONFIG.get(provider, {})
    api_base = pconfig.get("api_base", "")

    if provider == "anthropic":
        return _call_anthropic(api_key, model_id, messages)
    elif provider == "baidu":
        return _call_baidu(api_key, model_id, messages)
    else:
        return _call_openai_compatible(api_base, api_key, model_id, messages)


def _build_vision_messages(prompt, image_base64, model_info):
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            ],
        }
    ]


def _build_text_messages(prompt):
    return [{"role": "user", "content": prompt}]


def recognize_captcha(image_path=None, region=None, prompt="请识别图中的验证码，只输出验证码内容，不要输出其他文字", config=None):
    if config is None:
        config = load_config()

    model_key = config.get("vision_model", "glm-4v-flash")
    model_info = MODEL_REGISTRY.get(model_key)
    if not model_info:
        logger.error("未知的视觉模型: %s", model_key)
        return None

    if "vision" not in model_info["capabilities"]:
        logger.error("模型 %s 不支持视觉识别", model_key)
        return None

    provider = model_info["provider"]
    api_key = _get_api_key(config, provider)
    if not api_key:
        logger.error("未配置 %s 的 API Key", provider)
        return None

    if image_path and os.path.exists(image_path):
        img_b64 = _encode_image_base64(image_path)
    elif region:
        tmp_path = os.path.join(os.path.expanduser("~"), "GhostAction", "tmp_captcha.png")
        _screenshot_region(region[0], region[1], region[2], region[3], save_path=tmp_path)
        img_b64 = _encode_image_base64(tmp_path)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    else:
        logger.error("需要提供 image_path 或 region")
        return None

    messages = _build_vision_messages(prompt, img_b64, model_info)

    try:
        result = _dispatch_call(provider, api_key, model_info["model_id"], messages)
        logger.info("AI识别结果: %s (模型: %s)", result, model_key)
        return result.strip()
    except Exception as e:
        logger.error("AI识别失败: %s (模型: %s)", e, model_key)
        return None


def recognize_text(prompt, config=None):
    if config is None:
        config = load_config()

    model_key = config.get("text_model", "deepseek-chat")
    model_info = MODEL_REGISTRY.get(model_key)
    if not model_info:
        logger.error("未知的文本模型: %s", model_key)
        return None

    provider = model_info["provider"]
    api_key = _get_api_key(config, provider)
    if not api_key:
        logger.error("未配置 %s 的 API Key", provider)
        return None

    messages = _build_text_messages(prompt)

    try:
        result = _dispatch_call(provider, api_key, model_info["model_id"], messages)
        logger.info("AI文本结果: %s (模型: %s)", result, model_key)
        return result.strip()
    except Exception as e:
        logger.error("AI文本识别失败: %s (模型: %s)", e, model_key)
        return None


def test_connection(model_key, api_key):
    model_info = MODEL_REGISTRY.get(model_key)
    if not model_info:
        return False, f"未知模型: {model_key}"
    provider = model_info["provider"]
    try:
        result = _dispatch_call(provider, api_key, model_info["model_id"], [{"role": "user", "content": "你好，请回复'连接成功'"}])
        return True, f"连接成功: {result[:50]}"
    except Exception as e:
        return False, f"连接失败: {e}"


def get_available_models(config=None):
    if config is None:
        config = load_config()
    available = []
    for key, info in MODEL_REGISTRY.items():
        provider = info["provider"]
        api_key = _get_api_key(config, provider)
        available.append({
            "key": key,
            "name": info["name"],
            "provider": provider,
            "capabilities": info["capabilities"],
            "free": info["free"],
            "description": info["description"],
            "has_key": bool(api_key),
        })
    return available


def generate_intent(events, meta=None, config=None):
    if config is None:
        config = load_config()

    steps_summary = []
    for i, e in enumerate(events):
        etype = e.get("type", "")
        if etype == "mouse_down":
            btn = e.get("button", "left")
            win = e.get("window", {})
            win_name = win.get("owner", "") or win.get("title", "")
            ocr = e.get("ocr_anchor", {}).get("text", "")
            ax = e.get("ax_element", {})
            ax_title = ax.get("AXTitle", "")
            desc = f"步骤{i+1}: {'右键' if btn == 'right' else ''}点击"
            if ax_title:
                desc += f"「{ax_title}」"
            elif ocr:
                desc += f"「{ocr}」附近"
            if win_name:
                desc += f" (窗口:{win_name})"
            steps_summary.append(desc)
        elif etype == "key_down":
            text = e.get("text", "")
            mods = "+".join(e.get("modifiers", []))
            if text:
                steps_summary.append(f"步骤{i+1}: 输入「{text}」" + (f" (修饰键:{mods})" if mods else ""))
            elif mods:
                steps_summary.append(f"步骤{i+1}: 按快捷键 {mods}")
        elif etype == "scroll":
            dy = e.get("dy", 0)
            steps_summary.append(f"步骤{i+1}: {'向下' if dy > 0 else '向上'}滚动")
        elif etype == "mouse_drag":
            steps_summary.append(f"步骤{i+1}: 拖拽")

    if not steps_summary:
        return ""

    prompt = (
        "请分析以下桌面操作录制步骤，用一句话概括这个操作的整体意图（做什么事），"
        "然后用简短的短语描述每个步骤的目的。格式：\n"
        "意图：<一句话概括>\n"
        "步骤意图：\n"
        "1. <步骤1目的>\n"
        "2. <步骤2目的>\n"
        "...\n\n"
        "操作步骤：\n" + "\n".join(steps_summary)
    )

    result = recognize_text(prompt, config=config)
    if result:
        logger.info("AI意图生成: %s", result[:100])
    return result or ""


def locate_on_screen(image_path, target_description, config=None):
    if config is None:
        config = load_config()

    model_key = config.get("vision_model", "glm-4v-flash")
    model_info = MODEL_REGISTRY.get(model_key)
    if not model_info or "vision" not in model_info.get("capabilities", []):
        logger.warning("AI视觉模型不可用，跳过屏幕理解定位")
        return None

    provider = model_info["provider"]
    api_key = _get_api_key(config, provider)
    if not api_key:
        logger.warning("未配置API Key，跳过AI屏幕理解定位")
        return None

    if not image_path or not os.path.exists(image_path):
        return None

    img_b64 = _encode_image_base64(image_path)

    prompt = (
        f"在截图中找到「{target_description}」的位置。"
        f"请返回其中心点的像素坐标，格式为 JSON: {{\"x\": 数字, \"y\": 数字}}\n"
        f"如果找不到，返回 {{\"x\": -1, \"y\": -1}}\n"
        f"只返回JSON，不要其他文字。"
    )

    messages = _build_vision_messages(prompt, img_b64, model_info)

    try:
        result = _dispatch_call(provider, api_key, model_info["model_id"], messages)
        if not result:
            return None
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        coords = json.loads(result)
        x, y = coords.get("x", -1), coords.get("y", -1)
        if x < 0 or y < 0:
            logger.info("AI屏幕理解: 未找到「%s」", target_description)
            return None
        logger.info("AI屏幕理解: 「%s」位于 (%d, %d)", target_description, x, y)
        return (x, y)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("AI屏幕理解定位失败: %s", e)
        return None


# ==================== 离线AI引擎 (v1.7.0) ====================

def is_online(timeout=3):
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except Exception:
        return False


def _enhance_captcha_image(image_path):
    try:
        import cv2
        import numpy as np
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        denoised = cv2.medianBlur(binary, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
        enhanced_path = image_path.replace(".png", "_enhanced.png")
        cv2.imwrite(enhanced_path, cleaned)
        return enhanced_path
    except Exception as e:
        logger.warning("验证码图像增强失败: %s", e)
        return None


def _local_ocr_recognize(image_path, lang="chi_sim+eng"):
    try:
        import pytesseract
        from PIL import Image
        enhanced = _enhance_captcha_image(image_path)
        paths = [enhanced, image_path] if enhanced else [image_path]
        best_result = ""
        for p in paths:
            img = Image.open(p)
            configs = [
                "--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                "--psm 8",
                "--psm 7",
                "--psm 6",
            ]
            for cfg in configs:
                try:
                    text = pytesseract.image_to_string(img, lang=lang, config=cfg).strip()
                    if text and len(text) >= 2 and len(text) > len(best_result):
                        best_result = text
                except Exception:
                    continue
            if enhanced and os.path.exists(enhanced):
                try:
                    os.remove(enhanced)
                except Exception:
                    pass
        if best_result:
            logger.info("本地OCR识别: %s", best_result)
        return best_result or None
    except Exception as e:
        logger.warning("本地OCR识别失败: %s", e)
        return None


def _trocr_available():
    try:
        import onnxruntime
        encoder_path = os.path.join(LOCAL_MODEL_DIR, "trocr_encoder.onnx")
        decoder_path = os.path.join(LOCAL_MODEL_DIR, "trocr_decoder.onnx")
        return os.path.exists(encoder_path) and os.path.exists(decoder_path)
    except ImportError:
        return False


def _trocr_recognize(image_path):
    if not _trocr_available():
        return None
    try:
        import onnxruntime as ort
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGB").resize((384, 384))
        pixel_values = np.array(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
        pixel_values = (pixel_values - 0.5) / 0.5
        pixel_values = pixel_values[np.newaxis, :]

        encoder_path = os.path.join(LOCAL_MODEL_DIR, "trocr_encoder.onnx")
        decoder_path = os.path.join(LOCAL_MODEL_DIR, "trocr_decoder.onnx")

        enc_session = ort.InferenceSession(encoder_path)
        enc_out = enc_session.run(None, {"pixel_values": pixel_values.astype(np.float32)})

        dec_session = ort.InferenceSession(decoder_path)
        encoder_hidden_states = enc_out[0]

        input_ids = np.array([[0]], dtype=np.int64)
        result_tokens = []
        for _ in range(64):
            dec_out = dec_session.run(None, {"input_ids": input_ids, "encoder_hidden_states": encoder_hidden_states})
            next_token = int(np.argmax(dec_out[0][0, -1]))
            if next_token == 2:
                break
            result_tokens.append(next_token)
            input_ids = np.array([[next_token]], dtype=np.int64)

        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("microsoft/trocr-small-printed")
        text = tokenizer.decode(result_tokens, skip_special_tokens=True)
        if text:
            logger.info("TrOCR本地识别: %s", text)
        return text or None
    except Exception as e:
        logger.warning("TrOCR识别失败: %s", e)
        return None


def _local_locate(target_description, image_path=None):
    try:
        import mss
        import pytesseract
        from PIL import Image
        import numpy as np

        if not image_path or not os.path.exists(image_path):
            return None

        img = Image.open(image_path)
        width, height = img.size
        regions = [
            (0, 0, width, height // 3),
            (0, height // 3, width, 2 * height // 3),
            (0, 2 * height // 3, width, height),
            (0, 0, width // 2, height),
            (width // 2, 0, width, height),
        ]

        target_lower = target_description.lower()
        for rx, ry, rw, rh in regions:
            crop = img.crop((rx, ry, rx + rw, ry + rh))
            data = pytesseract.image_to_data(crop, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
            for i, text in enumerate(data["text"]):
                if not text.strip():
                    continue
                if target_lower in text.lower():
                    cx = data["left"][i] + data["width"][i] // 2 + rx
                    cy = data["top"][i] + data["height"][i] // 2 + ry
                    logger.info("本地OCR定位: 「%s」→ (%d, %d)", target_description, cx, cy)
                    return (cx, cy)
        return None
    except Exception as e:
        logger.warning("本地OCR定位失败: %s", e)
        return None


def generate_intent_offline(events, meta=None):
    pid_names = (meta or {}).get("pid_names", {})
    steps = []
    for e in events:
        etype = e.get("type")
        win = pid_names.get(e.get("pid"), "")
        win_label = f"在{win}中" if win else ""
        if etype == "mouse_down":
            ocr = e.get("ocr_anchor", {}).get("text", "")
            ax = e.get("ax_element", {})
            ax_title = ax.get("AXTitle", "")
            target = ax_title or ocr or ""
            btn = "右键" if e.get("button") == "right" else "点击"
            steps.append(f"{win_label}{btn}「{target}」")
        elif etype == "key_down":
            text = e.get("text", "")
            mods = "+".join(e.get("modifiers", []))
            if text:
                steps.append(f"{win_label}输入「{text}」")
            elif mods:
                steps.append(f"{win_label}按{mods}快捷键")
        elif etype == "scroll":
            steps.append(f"{win_label}滚动")
        elif etype == "mouse_drag":
            steps.append(f"{win_label}拖拽")

    if not steps:
        return ""

    windows = set()
    for w in pid_names.values():
        if w:
            windows.add(w)

    intent = "、".join(windows) if windows else "桌面操作"
    action_summary = " → ".join(steps[:5])
    if len(steps) > 5:
        action_summary += f" 等{len(steps)}步"

    return f"意图：{intent}操作 | 步骤：{action_summary}"


def get_ai_status(config=None):
    if config is None:
        config = load_config()
    online = is_online()
    vision_key = config.get("vision_model", "glm-4v-flash")
    text_key = config.get("text_model", "deepseek-chat")
    vision_info = MODEL_REGISTRY.get(vision_key, {})
    text_info = MODEL_REGISTRY.get(text_key, {})
    vision_api_key = _get_api_key(config, vision_info.get("provider", ""))
    text_api_key = _get_api_key(config, text_info.get("provider", ""))

    return {
        "online": online,
        "cloud_vision": online and bool(vision_api_key),
        "cloud_text": online and bool(text_api_key),
        "local_ocr": True,
        "local_trocr": _trocr_available(),
        "local_locate": True,
        "offline_intent": True,
    }


def recognize_captcha_with_fallback(image_path=None, region=None, prompt="请识别图中的验证码，只输出验证码内容，不要输出其他文字", config=None):
    if config is None:
        config = load_config()

    tmp_path = None
    if not image_path and region:
        tmp_path = os.path.join(os.path.expanduser("~"), "GhostAction", "tmp_captcha.png")
        _screenshot_region(region[0], region[1], region[2], region[3], save_path=tmp_path)
        image_path = tmp_path

    if not image_path or not os.path.exists(image_path):
        return None

    try:
        result = recognize_captcha(image_path=image_path, prompt=prompt, config=config)
        if result:
            return result
    except Exception:
        pass

    logger.info("云端AI失败，尝试TrOCR本地识别")
    result = _trocr_recognize(image_path)
    if result:
        return result

    logger.info("TrOCR不可用，尝试本地OCR增强识别")
    result = _local_ocr_recognize(image_path)
    if result:
        return result

    return None


def recognize_text_with_fallback(prompt, config=None):
    if config is None:
        config = load_config()

    try:
        result = recognize_text(prompt, config=config)
        if result:
            return result
    except Exception:
        pass

    logger.info("云端文本AI失败，离网模式无法处理文本问答")
    return None


def generate_intent_with_fallback(events, meta=None, config=None):
    if config is None:
        config = load_config()

    try:
        result = generate_intent(events, meta, config=config)
        if result:
            return result
    except Exception:
        pass

    logger.info("AI意图生成失败，使用规则引擎")
    return generate_intent_offline(events, meta)


def locate_on_screen_with_fallback(image_path, target_description, config=None):
    if config is None:
        config = load_config()

    try:
        result = locate_on_screen(image_path, target_description, config=config)
        if result:
            return result
    except Exception:
        pass

    logger.info("AI屏幕理解失败，尝试本地OCR定位")
    return _local_locate(target_description, image_path)


def generate_script_from_description(description, config=None):
    if config is None:
        config = load_config()

    prompt = (
        "你是一个桌面自动化脚本生成器。用户描述一个操作目标，你需要生成GhostAction脚本的事件序列（JSON数组）。\n\n"
        "支持的事件类型和字段：\n"
        "- mouse_down: {type, x, y, button('left'/'right'), pid, window:{owner,title}}\n"
        "- key_down: {type, keycode, text, modifiers:['cmd','shift','ctrl','alt'], pid}\n"
        "- type_text: {type, text, variable, pid}\n"
        "- scroll: {type, dx, dy, pid}\n"
        "- wait_for: {type, strategy('template'/'ocr'/'time'), timeout}\n"
        "- comment: {type, text}\n"
        "- set_variable: {type, name, value}\n"
        "- for: {type, count, variable}\n"
        "- endfor: {type}\n"
        "- ai_recognize: {type, target, mode('vision'/'text'), prompt, variable}\n\n"
        "规则：\n"
        "1. 只生成用户描述的操作步骤，不要添加额外步骤\n"
        "2. 坐标用比例值(0.0-1.0)，运行时会自动适配屏幕\n"
        "3. 对于输入文字，优先用type_text而非key_down\n"
        "4. 对于不确定位置的点击，用ai_recognize代替mouse_down\n"
        "5. pid设为0，window设为{owner:'',title:''}\n"
        "6. 每个事件必须有type字段\n\n"
        "用户描述：{desc}\n\n"
        "请只输出JSON数组，不要输出其他内容。如果无法生成，输出空数组[]。"
    ).format(desc=description)

    result = recognize_text(prompt, config=config)
    if not result:
        return None

    try:
        json_start = result.index('[')
        json_end = result.rindex(']') + 1
        events = json.loads(result[json_start:json_end])
        if isinstance(events, list) and len(events) > 0:
            logger.info("AI生成脚本: %d个事件", len(events))
            return events
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("AI脚本JSON解析失败: %s", e)

    return None
