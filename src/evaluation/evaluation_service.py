from __future__ import annotations
from typing import Any, Dict, Tuple, Callable

from src.evaluation.llm_judge import judge_with_qwen, judge_with_mistral, judge_with_gemma


def _get_judge(model: str) -> Callable[..., Dict[str, Any]]:
    m = (model or "").strip().lower()
    if m == "qwen":
        return judge_with_qwen
    if m == "mistral":
        return judge_with_mistral
    if m == "gemma":
        return judge_with_gemma
    raise ValueError("model must be one of: qwen, mistral, gemma")


def _extract_cluster(record: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    cs = record.get("cluster_summary")
    if isinstance(cs, dict):
        summary_text = (cs.get("summary") or "").strip()
    elif isinstance(cs, str):
        summary_text = cs.strip()
    else:
        summary_text = ""

    articles = record.get("source_articles", [])
    parts = []
    if isinstance(articles, list):
        for a in articles:
            if isinstance(a, dict):
                t = (a.get("text") or "").strip()
                if t:
                    parts.append(t)
    source_text = "\n\n---\n\n".join(parts).strip()

    meta = {
        "article_batch_id": record.get("article_batch_id", "unknown"),
        "cluster_id": record.get("cluster_id", "unknown"),
        "category": record.get("category", "unknown"),
    }
    return source_text, summary_text, meta


def _extract_mega(record: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    ms = record.get("mega_summary")
    if isinstance(ms, dict):
        summary_text = (ms.get("summary") or "").strip()
    elif isinstance(ms, str):
        summary_text = ms.strip()
    else:
        summary_text = ""

    cluster_summaries = record.get("cluster_summaries", {})
    parts = []
    if isinstance(cluster_summaries, dict):
        for cluster_id, obj in cluster_summaries.items():
            if isinstance(obj, dict):
                cat = (obj.get("category") or "").strip()
                s = (obj.get("summary") or "").strip()
            else:
                cat, s = "", str(obj).strip()
            if s:
                header = f"[{cluster_id}]"
                if cat:
                    header += f" ({cat})"
                parts.append(f"{header}\n{s}")
    source_text = "\n\n---\n\n".join(parts).strip()

    meta = {
        "article_batch_id": record.get("article_batch_id", "unknown"),
        "cluster_id": "NA",
        "num_clusters": len(cluster_summaries) if isinstance(cluster_summaries, dict) else 0,
    }
    return source_text, summary_text, meta


def evaluate_record(record: Dict[str, Any], *, level: str, model: str) -> Dict[str, Any]:
    """
    Returns a standardized response dict with status + 4 metrics or failure.
    """
    try:
        judge_fn = _get_judge(model)
        lvl = (level or "").strip().lower()

        if lvl == "cluster":
            source_text, summary_text, meta = _extract_cluster(record)
        elif lvl == "mega":
            source_text, summary_text, meta = _extract_mega(record)
        else:
            raise ValueError("level must be 'cluster' or 'mega'")

        if not source_text:
            raise ValueError("Missing/empty SOURCE text for evaluation")
        if not summary_text:
            raise ValueError("Missing/empty SUMMARY text for evaluation")

        scores = judge_fn(source_text=source_text, summary_text=summary_text)

        # enforce the 4 keys
        out_scores = {
            "coherence": int(scores["coherence"]),
            "consistency": int(scores["consistency"]),
            "relevance": int(scores["relevance"]),
            "fluency": int(scores["fluency"]),
        }

        return {
            "status": "success",
            "level": lvl,
            "model": (model or "").lower(),
            "meta": meta,
            "scores": out_scores,
        }

    except Exception as e:
        # best-effort meta extraction for debugging
        meta = {
            "article_batch_id": record.get("article_batch_id", "unknown") if isinstance(record, dict) else "unknown",
            "cluster_id": record.get("cluster_id", "NA") if isinstance(record, dict) else "NA",
            "category": record.get("category", "unknown") if isinstance(record, dict) else "unknown",
        }
        return {
            "status": "failed",
            "level": (level or "").lower(),
            "model": (model or "").lower(),
            "meta": meta,
            "error": str(e),
        }
