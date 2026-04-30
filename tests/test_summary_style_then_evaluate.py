#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Real pipeline (NO manual summary stitching), aligned with *actual* backend routes:

1) POST /cluster_create
   - input: request_id, articles[], min_cluster_size
   - output: clusters[], article_summaries{article_id: summary}

2) POST /cluster_summarize
   - input: request_id, clusters[], articles[], article_summaries
   - output: clusters[] with cluster_id, article_ids, summary

3) For EACH cluster summary:
   - run 12 combos = 3 writing styles * 4 output formats:
     POST /summary_style
     input: request_id, summary, writing_style, output_format, institutional, article_ids(optional)
     output: styled_summary

4) Evaluate each styled summary:
   POST /evaluate_cluster
   input: request_id, cluster_summary, source_articles[], drop_fallbacks, evaluate_tone, evaluate_style, article_ids(optional)
   output: scores

All requests/responses/summaries/scores are saved under:
  data/output/cluster_summary_style_then_evaluate/<timestamp>/

Constraints:
- Reads only: data/input/articles.json
- Writes only: data/output/
- Script lives in tests/

Usage:
  # Terminal 1
  PYTHONPATH=src uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

  # Terminal 2
  python -m pip install requests
  CSW_BASE_URL=http://127.0.0.1:8000 CSW_N_ARTICLES=12 python tests/test_summary_style_then_evaluate.py

Env:
  CSW_BASE_URL         default http://127.0.0.1:8000
  CSW_N_ARTICLES       default 12
  CSW_MIN_CLUSTER_SIZE default 2
  CSW_INSTITUTIONAL    default false
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

INPUT_PATH = Path("data/input/articles.json")
OUT_ROOT = Path("data/output/cluster_summary_style_then_evaluate")

WRITING_STYLES = ["journalistic", "academic", "executive"]
OUTPUT_FORMATS = ["paragraph", "bullet_points", "tldr", "sections"]

# Actual server paths (from your openapi.json)
PATH_CLUSTER_CREATE = "/cluster_create"
PATH_CLUSTER_SUMMARIZE = "/cluster_summarize"
PATH_SUMMARY_STYLE = "/summary_style"
PATH_EVALUATE_CLUSTER = "/evaluate_cluster"


# ----------------------------
# IO helpers
# ----------------------------
def read_articles() -> List[Dict[str, Any]]:
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("articles", "items", "data"):
            if k in data and isinstance(data[k], list):
                return data[k]
    raise ValueError("Unrecognized structure in data/input/articles.json")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")


def safe_filename(s: str, max_len: int = 180) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return s[:max_len] if len(s) > max_len else s


# ----------------------------
# Article mapping (docs schema)
# ----------------------------
def article_to_api_article(a: Dict[str, Any], fallback_id: str) -> Dict[str, Any]:
    """
    Shared Article schema used by clustering endpoints:
    {
      "id": "string",
      "title": "string",
      "body": "string",
      "language": "string"
    }
    """
    art_id = a.get("id") or a.get("article_id") or a.get("uuid") or fallback_id
    title = a.get("title") or a.get("headline") or ""
    body = a.get("body") or a.get("content") or a.get("text") or a.get("description") or ""
    language = a.get("language") or a.get("lang") or "auto"
    return {"id": str(art_id), "title": str(title), "body": str(body), "language": str(language)}


def article_to_source_text(a: Dict[str, Any]) -> str:
    title = (a.get("title") or a.get("headline") or "").strip()
    body = (a.get("body") or a.get("content") or a.get("text") or a.get("description") or "").strip()
    if title and body:
        return f"{title}. {body}"
    return body or title


# ----------------------------
# HTTP helpers
# ----------------------------
def post_json(url: str, payload: Dict[str, Any], timeout: int = 900) -> Tuple[int, Any]:
    r = requests.post(url, json=payload, timeout=timeout)
    try:
        body = r.json()
    except Exception:
        body = {"_non_json_body": r.text}
    return r.status_code, body


def require_200(step_name: str, url: str, code: int, resp: Any, out_path: Path) -> None:
    if code == 200:
        return
    msg = f"{step_name} failed (HTTP {code}) at {url}. See {out_path}"
    if isinstance(resp, dict) and "detail" in resp:
        msg += f"\nServer detail: {resp['detail']}"
    raise SystemExit(msg)


def extract_eval_scores(resp: Any) -> Dict[str, Any]:
    if not isinstance(resp, dict):
        return {"_error": "non-dict response"}
    return {
        "status": resp.get("status"),
        "num_judges_used": resp.get("num_judges_used"),
        "scores": resp.get("scores"),
        "tone_score": resp.get("tone_score"),
        "style_score": resp.get("style_score"),
        "tone_status": resp.get("tone_status"),
        "style_status": resp.get("style_status"),
        "error_reasons": resp.get("error_reasons"),
    }


# ----------------------------
# Main pipeline
# ----------------------------
def main() -> None:
    base_url = os.environ.get("CSW_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    n_articles = int(os.environ.get("CSW_N_ARTICLES", "12"))
    min_cluster_size = int(os.environ.get("CSW_MIN_CLUSTER_SIZE", "2"))
    institutional = os.environ.get("CSW_INSTITUTIONAL", "false").strip().lower() == "true"

    if not INPUT_PATH.exists():
        raise SystemExit(f"Missing input file: {INPUT_PATH}")

    all_articles = read_articles()
    if not all_articles:
        raise SystemExit("articles.json is empty")

    # deterministic subset
    step = max(1, len(all_articles) // n_articles)
    selected_raw = all_articles[::step][:n_articles]
    api_articles = [article_to_api_article(a, fallback_id=f"idx_{i}") for i, a in enumerate(selected_raw)]

    # lookup for evaluation source texts (uses the same dict shape we send to API)
    by_id: Dict[str, Dict[str, Any]] = {a["id"]: a for a in api_articles}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_ROOT / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        run_dir / "selected_articles_meta.json",
        [
            {
                "i": i,
                "id": api_articles[i]["id"],
                "title": api_articles[i]["title"],
                "language": api_articles[i]["language"],
            }
            for i in range(len(api_articles))
        ],
    )

    # -----------------------------
    # 1) cluster_create
    # -----------------------------
    cluster_create_url = f"{base_url}{PATH_CLUSTER_CREATE}"
    cluster_create_req = {
        "request_id": f"{ts}__cluster_create",
        "articles": api_articles,
        "min_cluster_size": min_cluster_size,
    }
    write_json(run_dir / "request__cluster_create.json", cluster_create_req)

    code, resp = post_json(cluster_create_url, cluster_create_req, timeout=1800)
    out_cc = run_dir / "response__cluster_create.json"
    write_json(out_cc, {"http_status": code, "response": resp})
    require_200("cluster_create", cluster_create_url, code, resp, out_cc)

    clusters = resp.get("clusters") if isinstance(resp, dict) else None
    article_summaries = resp.get("article_summaries") if isinstance(resp, dict) else None
    if not isinstance(clusters, list) or not isinstance(article_summaries, dict):
        raise SystemExit("cluster_create response missing 'clusters' list or 'article_summaries' dict.")

    write_json(run_dir / "cluster_create__clusters.json", clusters)

    # -----------------------------
    # 2) cluster_summarize
    # FIX: cast cluster_id (int from cluster_create) to str (required by cluster_summarize schema)
    # -----------------------------
    cluster_summarize_url = f"{base_url}{PATH_CLUSTER_SUMMARIZE}"
    cluster_summarize_req = {
        "request_id": f"{ts}__cluster_summarize",
        "clusters": [
            {
                "cluster_id": str(c.get("cluster_id")),
                "article_ids": [str(x) for x in (c.get("article_ids") or [])],
            }
            for c in clusters
            if isinstance(c, dict)
        ],
        "articles": api_articles,
        "article_summaries": {str(k): str(v) for k, v in article_summaries.items()},
    }
    write_json(run_dir / "request__cluster_summarize.json", cluster_summarize_req)

    code2, resp2 = post_json(cluster_summarize_url, cluster_summarize_req, timeout=1800)
    out_cs = run_dir / "response__cluster_summarize.json"
    write_json(out_cs, {"http_status": code2, "response": resp2})
    require_200("cluster_summarize", cluster_summarize_url, code2, resp2, out_cs)

    cluster_summaries = resp2.get("clusters") if isinstance(resp2, dict) else None
    if not isinstance(cluster_summaries, list):
        raise SystemExit("cluster_summarize response missing 'clusters' list.")

    cluster_dir = run_dir / "cluster_summaries"
    cluster_dir.mkdir(parents=True, exist_ok=True)

    style_dir = run_dir / "summary_style"
    style_dir.mkdir(parents=True, exist_ok=True)

    eval_dir = run_dir / "cases"
    eval_dir.mkdir(parents=True, exist_ok=True)

    results_summary: List[Dict[str, Any]] = []

    summary_style_url = f"{base_url}{PATH_SUMMARY_STYLE}"
    evaluate_url = f"{base_url}{PATH_EVALUATE_CLUSTER}"

    # -----------------------------
    # 3) style 12 combos + 4) evaluate
    # -----------------------------
    for ci, cobj in enumerate(cluster_summaries):
        if not isinstance(cobj, dict):
            continue

        cluster_id = cobj.get("cluster_id")
        c_article_ids = cobj.get("article_ids") or []
        c_summary = cobj.get("summary") or ""
        if not str(c_summary).strip():
            continue

        ctag = safe_filename(f"cluster_{ci}__{cluster_id}")
        write_text(cluster_dir / f"{ctag}__summary.txt", str(c_summary))

        # evaluation expects list of source article full texts
        source_articles: List[str] = []
        for aid in c_article_ids:
            a = by_id.get(str(aid))
            if a:
                t = article_to_source_text(a)
                if t.strip():
                    source_articles.append(t)

        if not source_articles:
            # fallback: evaluate against all selected articles
            source_articles = [article_to_source_text(a) for a in api_articles if article_to_source_text(a).strip()]

        for style in WRITING_STYLES:
            for fmt in OUTPUT_FORMATS:
                tag = safe_filename(f"{ctag}__{style}__{fmt}__inst_{institutional}")

                # 3) /summary_style
                style_req = {
                    "request_id": f"{ts}__{tag}",
                    "summary": str(c_summary),
                    "writing_style": style,
                    "output_format": fmt,
                    "institutional": institutional,
                    "article_ids": [str(x) for x in c_article_ids] if c_article_ids else None,
                }
                write_json(style_dir / f"request__{tag}.json", style_req)
                scode, sresp = post_json(summary_style_url, style_req, timeout=900)
                write_json(style_dir / f"response__{tag}.json", {"http_status": scode, "response": sresp})

                if scode != 200 or not isinstance(sresp, dict):
                    results_summary.append(
                        {
                            "cluster": ctag,
                            "cluster_id": cluster_id,
                            "combo": {"writing_style": style, "output_format": fmt, "institutional": institutional},
                            "summary_style_http_status": scode,
                            "evaluate_http_status": None,
                            "scores": None,
                            "error": "summary_style_failed",
                        }
                    )
                    continue

                styled_summary = sresp.get("styled_summary", "")
                write_text(style_dir / f"styled_summary__{tag}.txt", str(styled_summary))

                # 4) /evaluate_cluster
                eval_req = {
                    "request_id": f"{ts}__eval__{tag}",
                    "cluster_summary": str(styled_summary),
                    "source_articles": source_articles,
                    "drop_fallbacks": True,
                    "evaluate_tone": True,
                    "evaluate_style": True,
                    "cluster_id": str(cluster_id) if cluster_id is not None else None,
                    "article_ids": [str(x) for x in c_article_ids] if c_article_ids else None,
                }
                write_json(eval_dir / f"request__evaluate__{tag}.json", eval_req)
                ecode, eresp = post_json(evaluate_url, eval_req, timeout=1800)
                write_json(eval_dir / f"response__evaluate__{tag}.json", {"http_status": ecode, "response": eresp})

                results_summary.append(
                    {
                        "cluster": ctag,
                        "cluster_id": cluster_id,
                        "combo": {"writing_style": style, "output_format": fmt, "institutional": institutional},
                        "summary_style_http_status": scode,
                        "evaluate_http_status": ecode,
                        "scores": extract_eval_scores(eresp),
                    }
                )

    write_json(run_dir / "evaluation_scores_summary.json", results_summary)

    print(f"Done. Outputs saved to: {run_dir}")
    print("Key files:")
    print(f"  - {run_dir}/response__cluster_create.json")
    print(f"  - {run_dir}/response__cluster_summarize.json")
    print(f"  - {run_dir}/summary_style/ (all style req/resp + styled_summary txt)")
    print(f"  - {run_dir}/cases/ (all eval req/resp)")
    print(f"  - {run_dir}/evaluation_scores_summary.json")


if __name__ == "__main__":
    main()
