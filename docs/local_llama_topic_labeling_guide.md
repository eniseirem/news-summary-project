# Local LLaMA Topic Labeling Guide

**LLM Team – Milestone 2**
**Updated: 2025-12-05**

This guide explains how to run the local LLaMA backend and test our topic-labeling pipeline using Theresia’s new test scripts:
`test_topic_labeler_export.py`
`generate_topic_labels_to_csv.py`

The goal is:

> **Local JSON → LLaMA → Topic Labels → Saved JSON + CSV Output**
---

# 1. Prerequisites

### You need:

- Python virtual environment (.venv)
- Ollama installed
→ https://ollama.com/download

- LLaMA model pulled locally
(we use llama3)

Verify installation:
```bash
ollama --version
```
---

# 2. Pull the LLaMA Model

We use the default LLaMA 3:

ollama pull llama3

# 3. Terminal Setup (Important!)

Local topic labeling requires two terminals:

## Terminal 1 — Start Ollama Server

Run:
```bash
ollama serve
```

Keep this terminal open.
The LLaMA topic labeler script sends all requests to this server.

## Terminal 2 — Run the Topic Labeling Scripts

Activate the virtual environment:
```bash
cd cswspws25
source .venv/Scripts/activate     # Windows: .venv\Scripts\activate
```

Navigate to src:
```bash
cd src
```

There are two ways to test:

# 4. Option A — Run Full JSON Processing with Metrics

Script:
```bash
python -m llm_engine.test_topic_labeler_export
```

This will:

Load
`m2_articles_1.json`
`m2_articles_2.json`

Send each article to LLaMA topic labeler

Save results to:
`topic_label_results.json` 


Print:

- each article's category

- LLaMA prediction

- match comparison

At the end, output summary statistics:

- total articles

- number of matches

- accuracy

This run takes several minutes because every article goes through LLaMA.

# 5. Option B — Generate CSV Output

After running the export script, you can convert the JSON results into a CSV using:
```bash
python -m llm_engine.generate_topic_labels_to_csv
```

This script will:

Read `topic_label_results.json`

Convert all entries into a table

Save to:

`topic_label_results.csv`

This is the file to share with the team for analysis.

# 6. Summary

To run the complete topic labeling pipeline locally:

Terminal 1 → ollama serve

Terminal 2 → Activate venv and run:

Option A: Full labeling + JSON
```bash
python -m llm_engine.test_topic_labeler_export
```

Option B: Convert results to CSV
```bash
python -m llm_engine.generate_topic_labels_to_csv
```

If Terminal 1 is closed, LLaMA will not respond and the scripts will fail.