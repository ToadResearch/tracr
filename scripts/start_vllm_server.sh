#!/usr/bin/env bash
set -euo pipefail

show_help() {
  echo "Usage: $0 <model> [num_gpus] [port] [gpu_memory_utilization] [max_model_len] [data_parallel_size]"
  echo ""
  echo "Examples:"
  echo "  $0 lightonai/LightOnOCR-2-1B"
  echo "  $0 lightonai/LightOnOCR-2-1B 2 9000 0.90"
  echo "  $0 lightonai/LightOnOCR-2-1B 1 9000 0.90 8192 1"
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" || $# -lt 1 ]]; then
  show_help
  exit 0
fi

MODEL="$1"
NUM_GPUS="${2:-1}"
PORT="${3:-9000}"
GPU_MEM_UTIL="${4:-0.90}"
MAX_MODEL_LEN="${5:-}"
DATA_PARALLEL_SIZE="${6:-1}"

CMD=(
  uv run tracr vllm-launch "$MODEL"
  --num-gpus "$NUM_GPUS"
  --data-parallel-size "$DATA_PARALLEL_SIZE"
  --port "$PORT"
  --gpu-memory-utilization "$GPU_MEM_UTIL"
)

if [[ -n "$MAX_MODEL_LEN" ]]; then
  CMD+=(--max-model-len "$MAX_MODEL_LEN")
fi

echo "Starting vLLM with model: $MODEL"
printf 'Command: %q ' "${CMD[@]}"
echo
exec "${CMD[@]}"
