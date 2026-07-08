import os
import csv
import json
import logging

logger = logging.getLogger("data_source")


def read_csv(path, encoding="utf-8"):
    rows = []
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cleaned = {k.strip(): v.strip() for k, v in row.items() if k and k.strip()}
                rows.append(cleaned)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="gbk", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cleaned = {k.strip(): v.strip() for k, v in row.items() if k and k.strip()}
                    rows.append(cleaned)
        except Exception as e:
            logger.error("读取CSV失败: %s", e)
            return []
    except Exception as e:
        logger.error("读取CSV失败: %s", e)
        return []
    return rows


def read_excel(path):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = next(rows_iter, None)
        if not headers:
            wb.close()
            return []
        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(headers)]
        rows = []
        for row in rows_iter:
            d = {}
            for i, val in enumerate(row):
                if i < len(headers):
                    d[headers[i]] = str(val).strip() if val is not None else ""
            rows.append(d)
        wb.close()
        return rows
    except ImportError:
        logger.error("需要安装openpyxl: pip install openpyxl")
        return []
    except Exception as e:
        logger.error("读取Excel失败: %s", e)
        return []


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            return [data]
        return []
    except Exception as e:
        logger.error("读取JSON失败: %s", e)
        return []


def read_file(path):
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return read_csv(path)
    elif ext in (".xlsx", ".xls"):
        return read_excel(path)
    elif ext == ".json":
        return read_json(path)
    else:
        logger.error("不支持的文件格式: %s", ext)
        return []


def get_columns(rows):
    if not rows:
        return []
    cols = []
    seen = set()
    for row in rows:
        for k in row:
            if k not in seen:
                cols.append(k)
                seen.add(k)
    return cols


def resolve_variable(text, row_data):
    if not text or "{{" not in text:
        return text
    result = text
    for key, value in row_data.items():
        placeholder = "{{" + key + "}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    return result