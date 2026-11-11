#!/usr/bin/env bash
# Explicit network-enabled provisioning; normal inference uses only the private Compose network.
set -euo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$repo_dir/models/reviewer"
docker run --rm \
  --cap-drop ALL --security-opt no-new-privileges --read-only \
  --tmpfs /tmp:size=64m,mode=1777 --tmpfs /root/.ollama:size=4m,mode=0700 \
  -v "$repo_dir/models/reviewer:/models" \
  -e OLLAMA_MODELS=/models -e OLLAMA_HOST=127.0.0.1:11434 \
  -e REVIEWER_MODEL="${REVIEWER_MODEL:-qwen3:4b-instruct}" \
  --entrypoint /bin/sh \
  ollama/ollama@sha256:a372a1c0d1e15b68e9521189785c3ca17795c26c2356f8b1b10122cfb59ed0d7 \
  -c 'ollama serve & model_server=$!; trap "kill $model_server" EXIT; for attempt in $(seq 1 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done; ollama pull "$REVIEWER_MODEL"; ollama list'
