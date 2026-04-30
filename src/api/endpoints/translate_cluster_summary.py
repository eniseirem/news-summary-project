"""
translate_cluster_summary.py
============================

Translation endpoint for cluster summaries (English to German).

Purpose
-------
Translates cluster summaries from English to German using MarianMT translation model.
Adds translated summary as `summary_de` field to the cluster summary object.

Processing
----------
- Accepts cluster summary JSON object in request payload
- Extracts `cluster_summary.summary` field (English text)
- Translates summary to German using translate_en_to_de()
- Adds `summary_de` field to cluster_summary object
- Returns same payload structure with translated field added

Notes
-----
- If summary is empty or missing, sets `summary_de` to empty string
- Preserves all other fields in the payload unchanged
- Translation model: Helsinki-NLP/opus-mt-en-de
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm_engine.translate_en_to_de import translate_en_to_de

router = APIRouter(tags=["translation"])


class ClusterSummaryTranslateRequest(BaseModel):
    """
    Accepts the cluster summary JSON object.
    We only translate: cluster_summary.summary
    """
    payload: Dict[str, Any]


class ClusterSummaryTranslateResponse(BaseModel):
    payload: Dict[str, Any]


@router.post("/translate_cluster_summary", response_model=ClusterSummaryTranslateResponse)
def translate_cluster_summary_de(req: ClusterSummaryTranslateRequest) -> ClusterSummaryTranslateResponse:
    data = dict(req.payload)

    cluster_summary = data.get("cluster_summary")
    if not isinstance(cluster_summary, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'cluster_summary' object")

    summary = cluster_summary.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        # If empty, just set empty string summary_de
        cluster_summary["summary_de"] = ""
        data["cluster_summary"] = cluster_summary
        return ClusterSummaryTranslateResponse(payload=data)

    # Translate and attach
    cluster_summary["summary_de"] = translate_en_to_de(summary)
    data["cluster_summary"] = cluster_summary

    return ClusterSummaryTranslateResponse(payload=data)
