**LLM Team – Milestone 2**  
**Updated: 2025-12-07**

This guide explains how to **run the LLaMA backend locally and test the tone-rewriting prototype** using the official: using the official `src/llm_engine/test_summarize_batch_tones.py
` script.


---

# 1. Prerequisites

### You need:

- Python virtual environment (`.venv`)
- Ollama installed  
  → Download: https://ollama.com
- LLaMA model pulled (3B version)

Verify Ollama:

```bash
ollama --version
```

LLaMA Model Pulled Locally:


```bash
ollama pull llama3.2:3b
```

We use LLaMA 3.2 (3B) for local CPU testing.

---

# 2.  Start the Ollama Server

Ollama must be running in the background.
In a terminal window, start the server:
```bash
ollama serve
```
Leave this window open.

---
# 3.  Start the FastAPI Backend

In a second terminal window:

```bash
cd /path/to/cswspws25
source .venv/bin/activate
export PYTHONPATH=src
uvicorn api.main:app --reload
```
You should see:
```bash
Uvicorn running on http://127.0.0.1:8000
```

---
# 4. Run the Tone-Rewriting Test Script
In Terminal window #3:
```bash
cd /path/to/cswspws25
source .venv/bin/activate
export PYTHONPATH=src
python -m llm_engine.test_summarize_batch_tones
```

You should see output like:
```bash
=== LLaMA Batch Summary + Tone Rewriting Test ===

🔵 Testing tone = neutral
🔵 Testing tone = formal
🔵 Testing tone = conversational
...
```

---
# 5. Output Files

After running the test, results are automatically saved to:
```bash
cswspws25/data/output/test_tone_rewriting_results.json
```