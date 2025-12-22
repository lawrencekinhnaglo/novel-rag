#!/bin/bash
# Script to initialize Ollama with Qwen3:8b model

echo "Waiting for Ollama to be ready..."

# Wait for Ollama to be available
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    echo "Ollama not ready yet, waiting..."
    sleep 5
done

echo "Ollama is ready!"

# Check if qwen3:8b is already pulled
if curl -s http://localhost:11434/api/tags | grep -q "qwen3:8b"; then
    echo "qwen3:8b model already exists"
else
    echo "Pulling qwen3:8b model (this may take a while)..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "qwen3:8b"}' --no-buffer
    echo ""
    echo "qwen3:8b model pulled successfully!"
fi

echo "Ollama initialization complete!"

