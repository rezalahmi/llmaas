#!/bin/sh
set -e

echo "Starting Ollama..."
ollama serve &

# صبر تا آماده شدن سرور
until curl -s http://localhost:11434 > /dev/null; do
  sleep 2
done

echo "Ollama is up."

# ✅ Auto pull model اگر وجود ندارد
MODEL=gemma4:e4b

if ! ollama list | grep -q "$MODEL"; then
  echo "Pulling model $MODEL ..."
  ollama pull $MODEL
fi

wait
