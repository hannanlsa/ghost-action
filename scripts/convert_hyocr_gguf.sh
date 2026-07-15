#!/bin/bash
set -e

MODEL_DIR="/Users/panxiao/HunyuanOCR"
LLAMA_CPP="/Users/panxiao/llama.cpp"

echo "=== HunyuanOCR GGUF 转换工具 ==="

if [ ! -f "$MODEL_DIR/config.json" ]; then
    echo "ERROR: 模型未下载完成，请等待下载"
    exit 1
fi

cd "$LLAMA_CPP"

echo "1. 转换主模型为 GGUF (Q4_K_M 量化)..."
python3 convert_hf_to_gguf.py \
    --outfile "$MODEL_DIR/hyocr-f16.gguf" \
    --outtype f16 \
    "$MODEL_DIR"

echo "2. 转换 mmproj 为 GGUF..."
python3 convert_hf_to_gguf.py \
    --outfile "$MODEL_DIR/mmproj-hyocr-f16.gguf" \
    --outtype f16 \
    --mmproj \
    "$MODEL_DIR"

echo "3. 量化主模型为 Q4_K_M (更小更快)..."
./build/bin/llama-quantize \
    "$MODEL_DIR/hyocr-f16.gguf" \
    "$MODEL_DIR/hyocr-q4_k_m.gguf" \
    Q4_K_M

echo "4. 量化 mmproj 为 Q4_K_M..."
./build/bin/llama-quantize \
    "$MODEL_DIR/mmproj-hyocr-f16.gguf" \
    "$MODEL_DIR/mmproj-hyocr-q4_k_m.gguf" \
    Q4_K_M

echo ""
echo "=== 转换完成 ==="
echo "主模型: $MODEL_DIR/hyocr-q4_k_m.gguf"
echo "mmproj: $MODEL_DIR/mmproj-hyocr-q4_k_m.gguf"
ls -lh "$MODEL_DIR"/hyocr-q4_k_m.gguf "$MODEL_DIR"/mmproj-hyocr-q4_k_m.gguf