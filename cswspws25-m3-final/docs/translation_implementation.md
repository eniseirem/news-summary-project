# Translation Strategy (Milestone 2)

## 1. Background & Initial Decision

From the beginning of the pipeline design, we made a **deliberate decision to use English as the main processing language**.

### Why English as the main language?

- All summarization, clustering, topic labeling, and category labeling models are optimized for English
- Mixing languages inside embeddings and clustering would significantly degrade quality
- Keeping one internal language avoids combinatorial complexity

**Conclusion:**  
> All internal processing happens in English.

---

## 2. Phase 1: Input Normalization (German → English)

### What happens at ingestion time

When articles enter the system (from crawler / n8n):

- Articles may be in **English or German**
- German articles are **translated to English immediately**
- English articles pass through unchanged

This logic lives in:

- `llm_engine/multilingual.py`
- Used before clustering and summarization

### What is preserved

During this step we:
- Translate `title` and `body` → English
- Preserve metadata:
  - `original_language` is either "en" or "de"
  - original IDs
  - source / timestamps

After this phase, **all articles entering the pipeline are guaranteed to be English**.

This ensures:
- Stable embeddings
- Consistent clustering
- Predictable summarization behavior

---

## 3. Phase 2: Core Pipeline (English Only)

After normalization, the pipeline operates **entirely in English**:

- Article-level summarization
- Clustering
- Cluster summaries
- Mega summaries
- Topic labels
- Category labels

Key principle:
> The pipeline **never switches language internally**.

All outputs at this stage are English by design.

---

## 4. New Requirement: German Output for Frontend

### Problem

The frontend needs to:
- Display summaries in **German**
- Allow **language toggle (EN ⇄ DE)**
- Avoid running translation logic in the browser


---

## 5. Phase 3: Post-processing Translation (English → German)

### Core idea

Translation is introduced as a **pure post-processing step**, **after** all summarization is done.

Key rule:
> Translation never affects clustering, summarization, or labels.

---

## 6. What Is Translated (and What Is Not)

### ✅ Translated
- Cluster summary text  
  `cluster_summary.summary`
- Mega summary text  
  `mega_summary.summary`

### ❌ Not Translated
- Source articles
- Article titles / bodies
- Topic labels
- Category labels
- Keywords
- Clustering metadata

This keeps translation:
- Cheap
- Fast
- Deterministic
- Easy to maintain

---

## 7. Output Strategy

English summaries are always preserved.

German translations are added as **additional fields**:

```json
{
  "summary": "... English summary ...",
  "summary_de": "... German translation ..."
}

```
This allows:

- Frontend language toggle
- Backward compatibility
- Zero disruption to existing consumers

## 8. Translation Endpoints
To keep translation lightweight and decoupled, two separate endpoints are introduced.
### 8.1 Translate Cluster Summary
Endpoint
```bash
POST /translate/cluster_summary
```
Input
```bash
{
  "payload": {
    "cluster_summary": {
      "summary": "Hello world. This is a test."
    }
  }
}
```
Output
```bash
{
  "payload": {
    "cluster_summary": {
      "summary": "Hello world. This is a test.",
      "summary_de": "Das ist ein Test."
    }
  }
}

```

### 8.2 Translate Mega Summary
Endpoint
```bash
POST /translate/mega_summary
```

Input
```bash
{
  "payload": {
    "mega_summary": {
      "summary": "Hello world. This is a test."
    }
  }
}
```
Output
```bash
{
  "payload": {
    "mega_summary": {
      "summary": "Hello world. This is a test.",
      "summary_de": "Das ist ein Test."
    }
  }
}

```

## 9. Why IDs are not part of the API
The translation endpoints intentionally do not handle IDs:

- No cluster_id
- No article_id
- No batch_id

Reason:

- Translation does not own identity
- Mapping summaries back to clusters is handled by n8n / frontend
- Avoids tight coupling with upstream schemas

## 10. Model Choice

- Model: Helsinki-NLP/opus-mt-en-de
- Framework: Hugging Face Transformers (MarianMT)
- Execution: Local inference
- Max tokens: 512 (safe due to summary-level input)

## 11. End-to-End Flow Summary

```text
Input articles (EN / DE)
        ↓
Normalize to English (multilingual.py)
        ↓
Clustering & Summarization (English only)
        ↓
cluster_summary / mega_summary
        ↓
(optional) translation endpoint
        ↓
summary_de added for frontend toggle
