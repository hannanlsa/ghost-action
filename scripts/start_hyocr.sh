#!/bin/bash
set -e

LLAMA_SERVER="/Users/panxiao/llama.cpp/build/bin/llama-server"
MODEL_PATH="${HYOCR_MODEL_PATH:-/Users/panxiao/HunyuanOCR/hyocr-q4_k_m.gguf}"
MMPROJ_PATH="${HYOCR_MMPROJ_PATH:-/Users/panxiao/HunyuanOCR/mmproj-hyocr-q4_k_m.gguf}"
PORT="${HYOCR_PORT:-18433}"
CTX_SIZE="${HYOCR_CTX_SIZE:-8192}"
N_PREDICT="${HYOCR_N_PREDICT:-4096}"

echo "=== 启动 HunyuanOCR llama-server ==="

if [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: 模型文件不存在: $MODEL_PATH"
    echo "请先运行: bash scripts/convert_hyocr_gguf.sh"
    exit 1
fi

MMPROJ_ARGS=""
if [ -f "$MMPROJ_PATH" ]; then
    MMPROJ_ARGS="--mmproj $MMPROJ_PATH"
    echo "mmproj: $MMPROJ_PATH"
else
    echo "WARNING: mmproj 未找到，视觉功能可能不可用"
fi

echo "主模型: $MODEL_PATH"
echo "端口: $PORT"
echo ""

"$LLAMA_SERVER" \
    --model "$MODEL_PATH" \
    $MMPROJ_ARGS \
    --host 127.0.0.1 \
    --port "$PORT" \
    --ctx-size "$CTX_SIZE" \
    --n-predict "$N_PREDICT" \
    --threads 4 \
    --alias HYVL