import os
import json
import logging
import base64
import time

logger = logging.getLogger("ai_recognizer")

CONFIG_PATH = os.path.join(os.path.expanduser("~"), "GhostAction", "ai_config.json")

MODEL_REGISTRY = {
    "glm-4v-flash": {
        "name": "GLM-4V Flash",
        "provider": "zhipu",
        "capabilities": ["vision", "text"],
        "free": True,
        "api_base": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model_id": "glm-4v-flash",
        "description": "智谱免费视觉模型，擅长验证码/图表识别",
    },
    "glm-4v-plus": {
        "name": "GLM-4V Plus",
        "provider": "zhipu",
        "capabilities": ["vision", "text"],
        "free": False,
        "api_base": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model_id": "glm-4v-plus",
        "description": "智谱付费视觉模型，更强识别能力",
    },
    "deepseek-chat": {
        "name": "DeepSeek Chat",
        "provider": "deepseek",
        "capabilities": ["text"],
        "free": True,
        "api_base": "https://api.deepseek.com/chat/completions",
        "model_id": "deepseek-chat",
        "description": "DeepSeek免费文本模型，擅长逻辑推理",
    },
    "deepseek-reasoner": {
        "name": "DeepSeek Reasoner",
        "provider": "deepseek",
        "capabilities": ["text"],
        "free": False,
        "api_base": "https://api.deepseek.com/chat/completions",
        "model_id": "deepseek-reasoner",
        "description": "DeepSeek付费推理模型",
    },
    "qwen-vl-plus": {
        "name": "Qwen-VL Plus",
        "provider": "dashscope",
        "capabilities": ["vision", "text"],
        "free": True,
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model_id": "qwen-vl-plus",
        "description": "通义千问免费视觉模型",
    },
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "providers": {
            "zhipu": {"api_key": "", "enabled": True},
            "deepseek": {"api_key": "", "enabled": True},
            "dashscope": {"api_key": "", "enabled": True},
        },
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


def _call_zhipu(api_key, model_id, messages):
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
    resp = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_deepseek(api_key, model_id, messages):
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
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_dashscope(api_key, model_id, messages):
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
    resp = requests.post(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _build_vision_messages(prompt, image_base64, model_info):
    provider = model_info["provider"]
    if provider in ("zhipu", "dashscope"):
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                ],
            }
        ]
    elif provider == "deepseek":
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                ],
            }
        ]
    return [{"role": "user", "content": prompt}]


def _build_text_messages(prompt):
    return [{"role": "user", "content": prompt}]


CALL_DISPATCH = {
    "zhipu": _call_zhipu,
    "deepseek": _call_deepseek,
    "dashscope": _call_dashscope,
}


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

    caller = CALL_DISPATCH.get(provider)
    if not caller:
        logger.error("不支持的服务商: %s", provider)
        return None

    try:
        result = caller(api_key, model_info["model_id"], messages)
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

    caller = CALL_DISPATCH.get(provider)
    if not caller:
        logger.error("不支持的服务商: %s", provider)
        return None

    try:
        result = caller(api_key, model_info["model_id"], messages)
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
    caller = CALL_DISPATCH.get(provider)
    if not caller:
        return False, f"不支持的服务商: {provider}"
    try:
        if "vision" in model_info["capabilities"]:
            result = caller(api_key, model_info["model_id"], [{"role": "user", "content": "你好，请回复'连接成功'"}])
        else:
            result = caller(api_key, model_info["model_id"], [{"role": "user", "content": "你好，请回复'连接成功'"}])
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