import os
import time
import logging
import numpy as np

logger = logging.getLogger("ui_detector")

MODEL_DIR = os.path.join(os.path.expanduser("~"), "GhostAction", "models")
UI_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8n-ui.onnx")

UI_CLASSES = {
    0: "button", 1: "input", 2: "link", 3: "checkbox",
    4: "radio", 5: "select", 6: "text_area", 7: "image",
    8: "icon", 9: "label", 10: "menu", 11: "tab",
}

INPUT_SIZE = 640
CONF_THRESHOLD = 0.35
IOU_THRESHOLD = 0.45


def _ensure_model():
    if os.path.exists(UI_MODEL_PATH):
        return UI_MODEL_PATH
    os.makedirs(MODEL_DIR, exist_ok=True)
    yolov8n_path = os.path.join(MODEL_DIR, "yolov8n.onnx")
    if os.path.exists(yolov8n_path):
        return yolov8n_path
    try:
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        model.export(format="onnx", imgsz=INPUT_SIZE)
        exported = os.path.join(os.path.dirname(model.ckpt_path) if hasattr(model, 'ckpt_path') else ".", "yolov8n.onnx")
        if os.path.exists(exported):
            import shutil
            shutil.move(exported, yolov8n_path)
            return yolov8n_path
    except Exception as e:
        logger.warning(f"[ui_detector] auto-export failed: {e}")
    return None


class UIDetector:
    def __init__(self):
        self._session = None
        self._model_path = None

    def _load(self):
        if self._session:
            return True
        model_path = _ensure_model()
        if not model_path:
            logger.warning("[ui_detector] no model available")
            return False
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(model_path, opts)
            self._model_path = model_path
            logger.info(f"[ui_detector] loaded: {model_path}")
            return True
        except Exception as e:
            logger.error(f"[ui_detector] load failed: {e}")
            return False

    def is_available(self):
        return self._load()

    def detect(self, image, conf_threshold=CONF_THRESHOLD):
        if not self._load():
            return []
        if isinstance(image, str):
            from PIL import Image
            image = Image.open(image).convert("RGB")
        if hasattr(image, 'convert'):
            image = np.array(image)
        if image is None:
            return []

        orig_h, orig_w = image.shape[:2]
        input_tensor = self._preprocess(image)
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: input_tensor})
        detections = self._postprocess(outputs, orig_w, orig_h, conf_threshold)
        return detections

    def _preprocess(self, img):
        h, w = img.shape[:2]
        scale = min(INPUT_SIZE / w, INPUT_SIZE / h)
        new_w, new_h = int(w * scale), int(h * scale)
        import cv2
        resized = cv2.resize(img, (new_w, new_h))
        padded = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
        pad_x = (INPUT_SIZE - new_w) // 2
        pad_y = (INPUT_SIZE - new_h) // 2
        padded[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)
        blob = np.expand_dims(blob, axis=0)
        blob = np.ascontiguousarray(blob)
        return blob

    def _postprocess(self, outputs, orig_w, orig_h, conf_threshold):
        output = outputs[0]
        if len(output.shape) == 3:
            output = output[0]
        output = output.transpose(1, 0)
        scale = min(INPUT_SIZE / orig_w, INPUT_SIZE / orig_h)
        pad_x = (INPUT_SIZE - int(orig_w * scale)) // 2
        pad_y = (INPUT_SIZE - int(orig_h * scale)) // 2

        results = []
        for det in output:
            obj_conf = det[4]
            if obj_conf < conf_threshold:
                continue
            class_conf = det[5:]
            class_id = int(np.argmax(class_conf))
            final_conf = obj_conf * class_conf[class_id]
            if final_conf < conf_threshold:
                continue
            cx, cy, bw, bh = det[:4]
            x1 = (cx - bw / 2 - pad_x) / scale
            y1 = (cy - bh / 2 - pad_y) / scale
            x2 = (cx + bw / 2 - pad_x) / scale
            y2 = (cy + bh / 2 - pad_y) / scale
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))
            class_name = UI_CLASSES.get(class_id, f"class_{class_id}")
            results.append({
                "class": class_name,
                "class_id": class_id,
                "confidence": float(final_conf),
                "bbox": {"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
                "center": {"x": int((x1 + x2) / 2), "y": int((y1 + y2) / 2)},
            })
        results = self._nms(results, IOU_THRESHOLD)
        return results

    def _nms(self, detections, iou_threshold):
        if not detections:
            return []
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            detections = [d for d in detections if self._iou(best["bbox"], d["bbox"]) < iou_threshold]
        return keep

    @staticmethod
    def _iou(a, b):
        x1 = max(a["x"], b["x"])
        y1 = max(a["y"], b["y"])
        x2 = min(a["x"] + a["width"], b["x"] + b["width"])
        y2 = min(a["y"] + a["height"], b["y"] + b["height"])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = a["width"] * a["height"]
        area_b = b["width"] * b["height"]
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0

    def detect_with_ocr(self, image, target_text=None, conf_threshold=CONF_THRESHOLD):
        detections = self.detect(image, conf_threshold)
        if not target_text or not detections:
            return detections
        try:
            import pytesseract
            from PIL import Image
            if isinstance(image, str):
                pil_img = Image.open(image)
            elif isinstance(image, np.ndarray):
                pil_img = Image.fromarray(image)
            else:
                pil_img = image
            for det in detections:
                bbox = det["bbox"]
                region = pil_img.crop((bbox["x"], bbox["y"],
                                       bbox["x"] + bbox["width"],
                                       bbox["y"] + bbox["height"]))
                text = pytesseract.image_to_string(region, lang="chi_sim+eng").strip()
                det["ocr_text"] = text
                if target_text.lower() in text.lower():
                    det["matched"] = True
        except Exception:
            pass
        return detections

    def find_element(self, image, target_class=None, target_text=None):
        detections = self.detect_with_ocr(image, target_text)
        if target_class:
            detections = [d for d in detections if d["class"] == target_class]
        if target_text:
            matched = [d for d in detections if d.get("matched")]
            if matched:
                return matched[0]
        if detections:
            return detections[0]
        return None