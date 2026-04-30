import os
import json
import re
from typing import Any, Optional, Union, Dict
from datetime import datetime
from pathlib import Path

import requests

# ------------------------------------------------------------
# Ollama-only backend (local, no cloud models)
# ------------------------------------------------------------

# Local Ollama models
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_QWEN_MODEL = os.getenv("OLLAMA_QWEN_MODEL", "qwen2.5:7b-instruct")
OLLAMA_MISTRAL_MODEL = os.getenv("OLLAMA_MISTRAL_MODEL", "mistral:7b-instruct")
OLLAMA_GEMMA_MODEL = os.getenv("OLLAMA_GEMMA_MODEL", "gemma2:9b")

# Debug output (only written on failure)
DEBUG_DIR = Path(os.getenv("JUDGE_DEBUG_DIR", "data/evaluation/debug"))
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Final fallback default (must be valid output)
DEFAULT_SCORES: dict[str, int] = {
    "coherence": 3,
    "consistency": 3,
    "relevance": 3,
    "fluency": 3,
}

# Optional metrics fallback defaults
DEFAULT_TONE_SCORE: int = 3
DEFAULT_STYLE_SCORE: int = 3

# Status labels (for aggregation / QA)
STATUS_SUCCESS = "success"
STATUS_REPAIRED = "repaired"
STATUS_FALLBACK = "fallback"

JUDGE_PROMPT = """
You are a form-filling evaluator for summarization quality.

You will be given a SOURCE text and a SUMMARY. Evaluate the SUMMARY against the SOURCE on four metrics.

Evaluation Criteria (1–5):
- Coherence: The collective quality of all sentences. The summary should be well-structured and well-organized. It should not be a heap of related information, but should build from sentence to sentence to a coherent body of information about a topic. (DUC / Dang, 2005)
- Consistency: The factual alignment between the summary and the source. A factually consistent summary contains only statements that are entailed by the source document. Penalize hallucinated facts or contradictions.
- Fluency: The quality of individual sentences. Sentences should have no formatting problems, capitalization errors, or obviously ungrammatical text (e.g., fragments, missing components) that make the text difficult to read. (DUC / Dang, 2005)
- Relevance: Selection of important content from the source. The summary should include only important information from the source. Penalize redundancies and excess/unimportant information.

Evaluation Steps:
1) Read the SOURCE and identify the main topic and key points.
2) Read the SUMMARY and compare it against the SOURCE.
3) Score each metric strictly according to the criteria above.
4) Use the full 1–5 scale when appropriate; do not default to 3.

Scoring:
- Each score MUST be an integer token in {1,2,3,4,5}.

Return ONLY valid JSON in this exact format:
{
  "coherence": 1|2|3|4|5,
  "consistency": 1|2|3|4|5,
  "relevance": 1|2|3|4|5,
  "fluency": 1|2|3|4|5
}

IMPORTANT:
- Output ONLY the JSON object.
- Do NOT include explanations.
- Do NOT output reasoning, steps, or any other text.
- Do NOT use markdown or code fences.
- If you output anything other than JSON, you fail.

""".strip()

TONE_JUDGE_PROMPT = """
You are a form-filling evaluator for editorial tone in summaries.

You will be given a SOURCE text and a SUMMARY. Evaluate ONLY the editorial tone of the SUMMARY.

Evaluation Criteria (1–5):
- Tone: The appropriateness and consistency of the editorial tone. Evaluate whether the tone is:
  * Neutral/Objective: Balanced, factual, no evaluative language, no editorial emphasis
  * Institutional: Formal, impersonal, cautious wording, avoids ideological framing, avoids marketing language, no slang, no humor, no emotionally loaded phrasing
  * Appropriate for the content: The tone should match the nature of the source material and intended audience

Scoring Guidelines:
- 5: Perfect tone for the content type, highly appropriate and consistent
- 4: Good tone with minor inconsistencies
- 3: Acceptable tone but some issues with appropriateness or consistency
- 2: Poor tone, inappropriate or inconsistent
- 1: Very poor tone, highly inappropriate or inconsistent

Evaluation Steps:
1) Read the SOURCE to understand the content type and context.
2) Read the SUMMARY and evaluate its editorial tone.
3) Score the tone strictly according to the criteria above.
4) Use the full 1–5 scale when appropriate; do not default to 3.

Scoring:
- The score MUST be an integer token in {1,2,3,4,5}.

Return ONLY valid JSON in this exact format:
{
  "tone": 1|2|3|4|5
}

IMPORTANT:
- Output ONLY the JSON object.
- Do NOT include explanations.
- Do NOT output reasoning, steps, or any other text.
- Do NOT use markdown or code fences.
- If you output anything other than JSON, you fail.

""".strip()

STYLE_JUDGE_PROMPT = """
You are a form-filling evaluator for writing style in summaries.

You will be given a SOURCE text and a SUMMARY. Evaluate ONLY the writing style of the SUMMARY.

Evaluation Criteria (1–5):
- Style: The appropriateness and consistency of the writing style. Evaluate whether the style is:
  * Journalistic: Clear, factual, inverted pyramid structure, objective reporting
  * Academic: Careful wording, hedged claims, formal structure
  * Executive: High-level, decision-focused, concise, strategic perspective
  * Appropriate for the content: The style should match the nature of the source material and intended audience

Scoring Guidelines:
- 5: Perfect style for the content type, highly appropriate and consistent
- 4: Good style with minor inconsistencies
- 3: Acceptable style but some issues with appropriateness or consistency
- 2: Poor style, inappropriate or inconsistent
- 1: Very poor style, highly inappropriate or inconsistent

Evaluation Steps:
1) Read the SOURCE to understand the content type and context.
2) Read the SUMMARY and evaluate its writing style.
3) Score the style strictly according to the criteria above.
4) Use the full 1–5 scale when appropriate; do not default to 3.

Scoring:
- The score MUST be an integer token in {1,2,3,4,5}.

Return ONLY valid JSON in this exact format:
{
  "style": 1|2|3|4|5
}

IMPORTANT:
- Output ONLY the JSON object.
- Do NOT include explanations.
- Do NOT output reasoning, steps, or any other text.
- Do NOT use markdown or code fences.
- If you output anything other than JSON, you fail.

""".strip()


def _extract_first_json_object(text: str) -> Optional[str]:
    """
    Extract the first complete JSON object {...} from text using brace matching.
    This avoids the "first { to last }" bug when multiple JSON objects appear.
    Returns None if not found.
    """
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _parse_json_strict(text: str) -> Any:
    if text is None:
        raise ValueError("Model returned None content")

    text = text.strip()
    if not text:
        raise ValueError("Model returned empty content")

    # 1) Remove <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 2) Remove markdown code fences like ```json ... ```
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    # 3) Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4) Extract first complete {...} JSON object (brace matching)
    candidate = _extract_first_json_object(text)
    if candidate:
        return json.loads(candidate)

    # 5) If still failing, show raw content for debugging
    raise ValueError(f"Could not parse JSON. Raw output was:\n{text}")


def _normalize_and_validate_scores(obj: Any) -> dict:
    """
    Ensures we always return:
      {"coherence": int(1..5), "consistency": int(1..5), "relevance": int(1..5), "fluency": int(1..5)}
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Judge JSON is not an object/dict: {type(obj).__name__}")

    # normalize keys: strip + lower
    norm: dict[str, Any] = {}
    for k, v in obj.items():
        kk = k.strip().lower() if isinstance(k, str) else str(k).strip().lower()
        norm[kk] = v

    required = ["coherence", "consistency", "relevance", "fluency"]
    missing = [k for k in required if k not in norm]
    if missing:
        raise KeyError(f"Missing keys: {missing}. Got keys={list(norm.keys())}")

    out: dict[str, int] = {}
    for k in required:
        v = norm[k]

        # Accept "4" as string
        if isinstance(v, str):
            sv = v.strip()
            if sv.isdigit():
                v = int(sv)

        if not isinstance(v, int):
            raise ValueError(f"Value for '{k}' is not int: {repr(norm[k])}")

        if v not in (1, 2, 3, 4, 5):
            raise ValueError(f"Value for '{k}' not in 1..5: {v}")

        out[k] = v

    return out


def _normalize_and_validate_tone_score(obj: Any) -> int:
    """
    Validates and returns a single tone score (1-5).
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Judge JSON is not an object/dict: {type(obj).__name__}")

    norm: dict[str, Any] = {}
    for k, v in obj.items():
        kk = k.strip().lower() if isinstance(k, str) else str(k).strip().lower()
        norm[kk] = v

    if "tone" not in norm:
        raise KeyError(f"Missing key: 'tone'. Got keys={list(norm.keys())}")

    v = norm["tone"]
    if isinstance(v, str):
        sv = v.strip()
        if sv.isdigit():
            v = int(sv)

    if not isinstance(v, int):
        raise ValueError(f"Value for 'tone' is not int: {repr(norm['tone'])}")

    if v not in (1, 2, 3, 4, 5):
        raise ValueError(f"Value for 'tone' not in 1..5: {v}")

    return v


def _normalize_and_validate_style_score(obj: Any) -> int:
    """
    Validates and returns a single style score (1-5).
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Judge JSON is not an object/dict: {type(obj).__name__}")

    norm: dict[str, Any] = {}
    for k, v in obj.items():
        kk = k.strip().lower() if isinstance(k, str) else str(k).strip().lower()
        norm[kk] = v

    if "style" not in norm:
        raise KeyError(f"Missing key: 'style'. Got keys={list(norm.keys())}")

    v = norm["style"]
    if isinstance(v, str):
        sv = v.strip()
        if sv.isdigit():
            v = int(sv)

    if not isinstance(v, int):
        raise ValueError(f"Value for 'style' is not int: {repr(norm['style'])}")

    if v not in (1, 2, 3, 4, 5):
        raise ValueError(f"Value for 'style' not in 1..5: {v}")

    return v


def _build_prompt(source_text: str, summary_text: str) -> str:
    return (
        f"{JUDGE_PROMPT}\n\n"
        f"SOURCE:\n{source_text.strip()}\n\n"
        f"SUMMARY:\n{summary_text.strip()}"
    )


def _build_tone_prompt(source_text: str, summary_text: str) -> str:
    return (
        f"{TONE_JUDGE_PROMPT}\n\n"
        f"SOURCE:\n{source_text.strip()}\n\n"
        f"SUMMARY:\n{summary_text.strip()}"
    )


def _build_style_prompt(source_text: str, summary_text: str) -> str:
    return (
        f"{STYLE_JUDGE_PROMPT}\n\n"
        f"SOURCE:\n{source_text.strip()}\n\n"
        f"SUMMARY:\n{summary_text.strip()}"
    )


def _safe_slug(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "unknown"
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:80] if len(s) > 80 else s


def _run_name_from_path(run_name: Optional[str]) -> Optional[str]:
    """
    Accept either:
      - "001_mega_summary" (already a name)
      - "data/input/001_mega_summary.json" (path)
    and returns a clean stem ("001_mega_summary") when possible.
    """
    if not run_name:
        return None
    raw = run_name.strip()
    if not raw:
        return None

    try:
        p = Path(raw)
        if p.suffix:
            return p.stem
        return raw
    except Exception:
        return raw


def _write_debug_output(
    *,
    backend: str,
    model: str,
    stage: str,
    run_name: Optional[str] = None,
    level: Optional[str] = None,
    article_batch_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    category: Optional[str] = None,
    text: Optional[str] = None,
) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    rn = _run_name_from_path(run_name)
    run = _safe_slug(rn or "unknown_run")

    lvl = _safe_slug(level or "NA")
    bid = _safe_slug(article_batch_id or "NA")
    cid = _safe_slug(cluster_id or "NA")
    cat = _safe_slug(category or "NA")

    mdl = _safe_slug(model)
    bkd = _safe_slug(backend)
    stg = _safe_slug(stage)

    filename = f"{bkd}_{mdl}_{run}_{lvl}_{bid}_{cid}_{cat}_{stg}_{ts}.txt"
    path = DEBUG_DIR / filename

    payload = text if (text is not None and text.strip()) else "<EMPTY OUTPUT>\n"
    path.write_text(payload, encoding="utf-8")
    return str(path)


def _ollama_chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Calls local Ollama chat endpoint.

    Improvements:
    - Force JSON output via `format: "json"` when supported.
    - If Ollama returns an error due to unsupported `format`, retry without it.
    - If `message.content` is empty but `message.thinking` exists, return thinking for debugging.
    """
    payload_with_format = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",  # try force JSON
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    def _do_post(payload: dict) -> dict:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        data = _do_post(payload_with_format)
    except Exception:
        # Retry without format if the server rejects it
        payload_no_format = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        data = _do_post(payload_no_format)

    msg = data.get("message") or {}
    content = (msg.get("content") or "").strip()
    thinking = (msg.get("thinking") or "").strip()

    if content:
        return content

    if thinking:
        return (
            "[THINKING_ONLY_OUTPUT]\n"
            "The model did not emit assistant content.\n"
            "Below is the raw reasoning output:\n\n"
            f"{thinking}"
        )

    return ""


def _as_meta_return(
    scores: dict[str, int],
    *,
    status: str,
    debug: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    return {
        "scores": scores,
        "status": status,
        "debug": debug or {},
        "error": error,
    }


def _judge(
    model: str,
    source_text: str,
    summary_text: str,
    *,
    temperature: float = 0,
    max_tokens: int = 200,
    use_system: bool = True,
    repair_max_tokens: int = 120,
    run_name: Optional[str] = None,
    # debug meta (optional)
    level: Optional[str] = None,
    article_batch_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    category: Optional[str] = None,
    # NEW: allow callers (aggregator) to receive status/debug metadata
    return_meta: bool = False,
) -> Union[dict, Dict[str, Any]]:
    prompt = _build_prompt(source_text, summary_text)

    def _call(messages: list[dict], *, t: float, mt: int, stage: str) -> str:
        try:
            return _ollama_chat(model=model, messages=messages, temperature=t, max_tokens=mt)
        except Exception as e:
            dbg_path = _write_debug_output(
                backend="ollama",
                model=model,
                stage=f"{stage}_request_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=f"{type(e).__name__}: {e}",
            )
            raise RuntimeError(f"{e} (debug saved to {dbg_path})") from e

    # --------------------
    # Attempt 1
    # --------------------
    messages: list[dict[str, str]] = []
    if use_system:
        messages.append({"role": "system", "content": "You are a strict, rubric-based evaluator. Output JSON only."})
    messages.append({"role": "user", "content": prompt})

    try:
        text = _call(messages, t=temperature, mt=max_tokens, stage="attempt1")
    except Exception as e_call:
        # Absolute fallback: never error
        dbg = _write_debug_output(
            backend="ollama",
            model=model,
            stage="final_fallback_used_call_error",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=f"CALL ERROR: {type(e_call).__name__}: {e_call}\nReturning DEFAULT_SCORES={DEFAULT_SCORES}",
        )
        scores = dict(DEFAULT_SCORES)
        if return_meta:
            return _as_meta_return(scores, status=STATUS_FALLBACK, debug={"call_error": dbg}, error=str(e_call))
        return scores

    try:
        parsed = _parse_json_strict(text)
        scores = _normalize_and_validate_scores(parsed)
        if return_meta:
            return _as_meta_return(scores, status=STATUS_SUCCESS, debug={}, error=None)
        return scores
    except Exception as e1:
        dbg_path1 = _write_debug_output(
            backend="ollama",
            model=model,
            stage="attempt1_raw_output",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=text,
        )

        # --------------------
        # Repair attempt
        # --------------------
        repair_prompt = (
            "Convert the following text into VALID JSON with EXACTLY these keys:\n"
            "coherence, consistency, relevance, fluency\n"
            "Each value must be an integer in {1,2,3,4,5}.\n"
            "Output ONLY the JSON object. No other text.\n\n"
            f"TEXT:\n{text}"
        )
        repair_messages: list[dict[str, str]] = []
        if use_system:
            repair_messages.append({"role": "system", "content": "Output JSON only."})
        repair_messages.append({"role": "user", "content": repair_prompt})

        try:
            text2 = _call(repair_messages, t=0, mt=repair_max_tokens, stage="repair")
        except Exception as e_call2:
            dbg = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used_repair_call_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    f"REPAIR CALL ERROR: {type(e_call2).__name__}: {e_call2}\n"
                    f"attempt1_debug={dbg_path1}\nReturning DEFAULT_SCORES={DEFAULT_SCORES}"
                ),
            )
            scores = dict(DEFAULT_SCORES)
            if return_meta:
                return _as_meta_return(
                    scores,
                    status=STATUS_FALLBACK,
                    debug={"attempt1": dbg_path1, "repair_call_error": dbg},
                    error=str(e_call2),
                )
            return scores

        try:
            parsed2 = _parse_json_strict(text2)
            scores = _normalize_and_validate_scores(parsed2)
            if return_meta:
                # repaired success: include attempt1 debug pointer for traceability
                return _as_meta_return(scores, status=STATUS_REPAIRED, debug={"attempt1": dbg_path1}, error=None)
            return scores
        except Exception as e2:
            dbg_path2 = _write_debug_output(
                backend="ollama",
                model=model,
                stage="repair_raw_output",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=text2,
            )

            # FINAL FALLBACK: never error; return default neutral scores.
            dbg_final = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    "FINAL FALLBACK USED. Returning DEFAULT_SCORES.\n\n"
                    f"attempt1_debug={dbg_path1}\n"
                    f"repair_debug={dbg_path2}\n"
                    f"attempt1_error={type(e1).__name__}: {e1}\n"
                    f"repair_error={type(e2).__name__}: {e2}\n"
                    f"DEFAULT_SCORES={DEFAULT_SCORES}\n"
                ),
            )

            scores = dict(DEFAULT_SCORES)
            if return_meta:
                return _as_meta_return(
                    scores,
                    status=STATUS_FALLBACK,
                    debug={"attempt1": dbg_path1, "repair": dbg_path2, "final": dbg_final},
                    error=f"attempt1={type(e1).__name__}: {e1} | repair={type(e2).__name__}: {e2}",
                )
            return scores


# Public wrappers (Ollama-only)
def judge_with_qwen(source_text: str, summary_text: str, **kwargs: Any) -> dict:
    return _judge(OLLAMA_QWEN_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_with_mistral(source_text: str, summary_text: str, **kwargs: Any) -> dict:
    return _judge(OLLAMA_MISTRAL_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_with_gemma(source_text: str, summary_text: str, **kwargs: Any) -> dict:
    return _judge(OLLAMA_GEMMA_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def _judge_tone(
    model: str,
    source_text: str,
    summary_text: str,
    *,
    temperature: float = 0,
    max_tokens: int = 100,
    use_system: bool = True,
    repair_max_tokens: int = 80,
    run_name: Optional[str] = None,
    level: Optional[str] = None,
    article_batch_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    category: Optional[str] = None,
    return_meta: bool = False,
) -> Union[int, Dict[str, Any]]:
    """
    Judge tone independently. Returns a single score (1-5) or dict with meta.
    """
    prompt = _build_tone_prompt(source_text, summary_text)

    def _call(messages: list[dict], *, t: float, mt: int, stage: str) -> str:
        try:
            return _ollama_chat(model=model, messages=messages, temperature=t, max_tokens=mt)
        except Exception as e:
            dbg_path = _write_debug_output(
                backend="ollama",
                model=model,
                stage=f"{stage}_request_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=f"{type(e).__name__}: {e}",
            )
            raise RuntimeError(f"{e} (debug saved to {dbg_path})") from e

    messages: list[dict[str, str]] = []
    if use_system:
        messages.append({"role": "system", "content": "You are a strict, rubric-based evaluator. Output JSON only."})
    messages.append({"role": "user", "content": prompt})

    try:
        text = _call(messages, t=temperature, mt=max_tokens, stage="attempt1")
    except Exception as e_call:
        dbg = _write_debug_output(
            backend="ollama",
            model=model,
            stage="final_fallback_used_call_error",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=f"CALL ERROR: {type(e_call).__name__}: {e_call}\nReturning DEFAULT_TONE_SCORE={DEFAULT_TONE_SCORE}",
        )
        score = DEFAULT_TONE_SCORE
        if return_meta:
            return {"score": score, "status": STATUS_FALLBACK, "debug": {"call_error": dbg}, "error": str(e_call)}
        return score

    try:
        parsed = _parse_json_strict(text)
        score = _normalize_and_validate_tone_score(parsed)
        if return_meta:
            return {"score": score, "status": STATUS_SUCCESS, "debug": {}, "error": None}
        return score
    except Exception as e1:
        dbg_path1 = _write_debug_output(
            backend="ollama",
            model=model,
            stage="attempt1_raw_output",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=text,
        )

        repair_prompt = (
            "Convert the following text into VALID JSON with EXACTLY this key:\n"
            "tone\n"
            "The value must be an integer in {1,2,3,4,5}.\n"
            "Output ONLY the JSON object. No other text.\n\n"
            f"TEXT:\n{text}"
        )
        repair_messages: list[dict[str, str]] = []
        if use_system:
            repair_messages.append({"role": "system", "content": "Output JSON only."})
        repair_messages.append({"role": "user", "content": repair_prompt})

        try:
            text2 = _call(repair_messages, t=0, mt=repair_max_tokens, stage="repair")
        except Exception as e_call2:
            dbg = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used_repair_call_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    f"REPAIR CALL ERROR: {type(e_call2).__name__}: {e_call2}\n"
                    f"attempt1_debug={dbg_path1}\nReturning DEFAULT_TONE_SCORE={DEFAULT_TONE_SCORE}"
                ),
            )
            score = DEFAULT_TONE_SCORE
            if return_meta:
                return {
                    "score": score,
                    "status": STATUS_FALLBACK,
                    "debug": {"attempt1": dbg_path1, "repair_call_error": dbg},
                    "error": str(e_call2),
                }
            return score

        try:
            parsed2 = _parse_json_strict(text2)
            score = _normalize_and_validate_tone_score(parsed2)
            if return_meta:
                return {"score": score, "status": STATUS_REPAIRED, "debug": {"attempt1": dbg_path1}, "error": None}
            return score
        except Exception as e2:
            dbg_path2 = _write_debug_output(
                backend="ollama",
                model=model,
                stage="repair_raw_output",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=text2,
            )

            dbg_final = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    "FINAL FALLBACK USED. Returning DEFAULT_TONE_SCORE.\n\n"
                    f"attempt1_debug={dbg_path1}\n"
                    f"repair_debug={dbg_path2}\n"
                    f"attempt1_error={type(e1).__name__}: {e1}\n"
                    f"repair_error={type(e2).__name__}: {e2}\n"
                    f"DEFAULT_TONE_SCORE={DEFAULT_TONE_SCORE}\n"
                ),
            )

            score = DEFAULT_TONE_SCORE
            if return_meta:
                return {
                    "score": score,
                    "status": STATUS_FALLBACK,
                    "debug": {"attempt1": dbg_path1, "repair": dbg_path2, "final": dbg_final},
                    "error": f"attempt1={type(e1).__name__}: {e1} | repair={type(e2).__name__}: {e2}",
                }
            return score


def _judge_style(
    model: str,
    source_text: str,
    summary_text: str,
    *,
    temperature: float = 0,
    max_tokens: int = 100,
    use_system: bool = True,
    repair_max_tokens: int = 80,
    run_name: Optional[str] = None,
    level: Optional[str] = None,
    article_batch_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    category: Optional[str] = None,
    return_meta: bool = False,
) -> Union[int, Dict[str, Any]]:
    """
    Judge style independently. Returns a single score (1-5) or dict with meta.
    """
    prompt = _build_style_prompt(source_text, summary_text)

    def _call(messages: list[dict], *, t: float, mt: int, stage: str) -> str:
        try:
            return _ollama_chat(model=model, messages=messages, temperature=t, max_tokens=mt)
        except Exception as e:
            dbg_path = _write_debug_output(
                backend="ollama",
                model=model,
                stage=f"{stage}_request_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=f"{type(e).__name__}: {e}",
            )
            raise RuntimeError(f"{e} (debug saved to {dbg_path})") from e

    messages: list[dict[str, str]] = []
    if use_system:
        messages.append({"role": "system", "content": "You are a strict, rubric-based evaluator. Output JSON only."})
    messages.append({"role": "user", "content": prompt})

    try:
        text = _call(messages, t=temperature, mt=max_tokens, stage="attempt1")
    except Exception as e_call:
        dbg = _write_debug_output(
            backend="ollama",
            model=model,
            stage="final_fallback_used_call_error",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=f"CALL ERROR: {type(e_call).__name__}: {e_call}\nReturning DEFAULT_STYLE_SCORE={DEFAULT_STYLE_SCORE}",
        )
        score = DEFAULT_STYLE_SCORE
        if return_meta:
            return {"score": score, "status": STATUS_FALLBACK, "debug": {"call_error": dbg}, "error": str(e_call)}
        return score

    try:
        parsed = _parse_json_strict(text)
        score = _normalize_and_validate_style_score(parsed)
        if return_meta:
            return {"score": score, "status": STATUS_SUCCESS, "debug": {}, "error": None}
        return score
    except Exception as e1:
        dbg_path1 = _write_debug_output(
            backend="ollama",
            model=model,
            stage="attempt1_raw_output",
            run_name=run_name,
            level=level,
            article_batch_id=article_batch_id,
            cluster_id=cluster_id,
            category=category,
            text=text,
        )

        repair_prompt = (
            "Convert the following text into VALID JSON with EXACTLY this key:\n"
            "style\n"
            "The value must be an integer in {1,2,3,4,5}.\n"
            "Output ONLY the JSON object. No other text.\n\n"
            f"TEXT:\n{text}"
        )
        repair_messages: list[dict[str, str]] = []
        if use_system:
            repair_messages.append({"role": "system", "content": "Output JSON only."})
        repair_messages.append({"role": "user", "content": repair_prompt})

        try:
            text2 = _call(repair_messages, t=0, mt=repair_max_tokens, stage="repair")
        except Exception as e_call2:
            dbg = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used_repair_call_error",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    f"REPAIR CALL ERROR: {type(e_call2).__name__}: {e_call2}\n"
                    f"attempt1_debug={dbg_path1}\nReturning DEFAULT_STYLE_SCORE={DEFAULT_STYLE_SCORE}"
                ),
            )
            score = DEFAULT_STYLE_SCORE
            if return_meta:
                return {
                    "score": score,
                    "status": STATUS_FALLBACK,
                    "debug": {"attempt1": dbg_path1, "repair_call_error": dbg},
                    "error": str(e_call2),
                }
            return score

        try:
            parsed2 = _parse_json_strict(text2)
            score = _normalize_and_validate_style_score(parsed2)
            if return_meta:
                return {"score": score, "status": STATUS_REPAIRED, "debug": {"attempt1": dbg_path1}, "error": None}
            return score
        except Exception as e2:
            dbg_path2 = _write_debug_output(
                backend="ollama",
                model=model,
                stage="repair_raw_output",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=text2,
            )

            dbg_final = _write_debug_output(
                backend="ollama",
                model=model,
                stage="final_fallback_used",
                run_name=run_name,
                level=level,
                article_batch_id=article_batch_id,
                cluster_id=cluster_id,
                category=category,
                text=(
                    "FINAL FALLBACK USED. Returning DEFAULT_STYLE_SCORE.\n\n"
                    f"attempt1_debug={dbg_path1}\n"
                    f"repair_debug={dbg_path2}\n"
                    f"attempt1_error={type(e1).__name__}: {e1}\n"
                    f"repair_error={type(e2).__name__}: {e2}\n"
                    f"DEFAULT_STYLE_SCORE={DEFAULT_STYLE_SCORE}\n"
                ),
            )

            score = DEFAULT_STYLE_SCORE
            if return_meta:
                return {
                    "score": score,
                    "status": STATUS_FALLBACK,
                    "debug": {"attempt1": dbg_path1, "repair": dbg_path2, "final": dbg_final},
                    "error": f"attempt1={type(e1).__name__}: {e1} | repair={type(e2).__name__}: {e2}",
                }
            return score


# Public wrappers for tone and style evaluation
def judge_tone_with_qwen(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_tone(OLLAMA_QWEN_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_tone_with_mistral(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_tone(OLLAMA_MISTRAL_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_tone_with_gemma(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_tone(OLLAMA_GEMMA_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_style_with_qwen(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_style(OLLAMA_QWEN_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_style_with_mistral(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_style(OLLAMA_MISTRAL_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)


def judge_style_with_gemma(source_text: str, summary_text: str, **kwargs: Any) -> Union[int, Dict[str, Any]]:
    return _judge_style(OLLAMA_GEMMA_MODEL, source_text, summary_text, temperature=0, use_system=True, **kwargs)
