#!/bin/bash
# Script to forcefully restart Ollama

echo "🔄 Restarting Ollama..."

# Kill all Ollama processes
echo "1. Killing Ollama processes..."
pkill -9 -f ollama 2>/dev/null
sleep 1

# Kill anything on port 11434
echo "2. Freeing port 11434..."
lsof -ti:11434 | xargs kill -9 2>/dev/null
sleep 2

# Check if Ollama is responding
echo "3. Checking Ollama status..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running and responding"
else
    echo "⚠️  Ollama is not responding. You may need to:"
    echo "   - Open the Ollama app manually, or"
    echo "   - Run: ollama serve"
fi

echo ""
echo "Done! Try your test again."
