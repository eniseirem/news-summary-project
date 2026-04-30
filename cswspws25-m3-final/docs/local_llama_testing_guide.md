# Local LLaMA Testing Guide  
**LLM Team – Milestone 2**  
**Updated: 2025-12-04**

This guide explains how to **run the LLaMA backend locally** and **test the summarization pipeline** using the official `test_llama_batch_local.py` script.

The goal is:

> **Local JSON → FastAPI → LLaMA → Mega Summary → Saved Output File**

This is the same flow that n8n/backend will use in production.

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
---

# 2.  Pull the LLaMA Model

We use LLaMA 3.2 (3B) for local CPU testing:

```bash
ollama pull llama3.2:3b
```
This downloads the 3B model used for local CPU/GPU testing.

---
# 3.  Terminal Setup (Important!)

Local testing requires three terminal windows, each running a separate service.

## Terminal 1 — Start Ollama Server
Run:
```bash
ollama serve
```

Keep this terminal open.
FastAPI and the test script will send requests to this server.


## Terminal 2 — Start FastAPI Backend


From the project root:
```bash
cd cswspws25
source .venv/bin/activate
```
Set the backend to LLaMA:
```bash
export LLM_BACKEND=llama
export OLLAMA_HOST=http://localhost:11434
```

Start FastAPI from inside the src/ folder:
```bash
cd src
uvicorn api.main:app --reload --port 8000
```
This must stay running — it provides the /summarize_batch endpoint.

## Terminal 3 — Run the Local LLaMA Batch Test Script
Open a new terminal, activate the venv again:
```bash
cd cswspws25
source .venv/bin/activate
```
Run the script from inside src/:
```bash
cd src
python -m llm_engine.test_llama_batch_local
```
This script will:

1. Load input file: `data/input/m2_articles_1.json`

2. Automatically wrap it into a valid BatchRequest format

3. Send the request to FastAPI endpoint `POST /summarize_batch`

4. Print the LLaMA-generated final summary to the terminal

5. Save the full output JSON to: `data/output/summary_m2_articles_1_llama.json`

# 4. Summary
To run the entire LLaMA summarization pipeline locally:

- Terminal 1 → ollama serve

- Terminal 2 → FastAPI (uvicorn)

- Terminal 3 → Run the LLaMA test script

If any of these terminals are closed, the pipeline will not function.