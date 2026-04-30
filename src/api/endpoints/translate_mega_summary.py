"""
translate_mega_summary.py
=========================

Translation endpoint for mega summaries (English to German).

Purpose
-------
Translates mega summaries and associated cluster summaries from English to German
using MarianMT translation model. Adds translated summaries as `summary_de` fields.

Processing
----------
- Accepts mega summary JSON object in request payload
- Translates `mega_summary.summary` → adds `mega_summary.summary_de`
- Translates all `cluster_summaries[cluster_id].summary` → adds `cluster_summaries[cluster_id].summary_de`
- Returns same payload structure with translated fields added

Notes
-----
- If summary is empty or missing, sets `summary_de` to empty string
- If cluster_summaries is missing, still translates mega_summary
- Preserves all other fields in the payload unchanged
- Translation model: Helsinki-NLP/opus-mt-en-de
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm_engine.translate_en_to_de import translate_en_to_de

router = APIRouter(tags=["translation"])


class MegaSummaryTranslateRequest(BaseModel):
    """
    Accepts the mega summary JSON object.
    We translate:
      - mega_summary.summary
      - cluster_summaries.*.summary
    """
    payload: Dict[str, Any]


class MegaSummaryTranslateResponse(BaseModel):
    payload: Dict[str, Any]


@router.post("/translate_mega_summary", response_model=MegaSummaryTranslateResponse)
def translate_mega_summary_de(req: MegaSummaryTranslateRequest) -> MegaSummaryTranslateResponse:
    data = dict(req.payload)

    # 1) Translate mega_summary.summary
    mega = data.get("mega_summary")
    if not isinstance(mega, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'mega_summary' object")

    mega_summary_text = mega.get("summary", "")
    if isinstance(mega_summary_text, str) and mega_summary_text.strip():
        mega["summary_de"] = translate_en_to_de(mega_summary_text)
    else:
        mega["summary_de"] = ""

    data["mega_summary"] = mega

    # 2) Translate each cluster_summaries[cluster_x].summary
    cluster_summaries = data.get("cluster_summaries")
    if cluster_summaries is None:
        # If there is no cluster_summaries, we still return mega_summary_de
        return MegaSummaryTranslateResponse(payload=data)

    if not isinstance(cluster_summaries, dict):
        raise HTTPException(status_code=400, detail="'cluster_summaries' must be a dict")

    out_cluster_summaries: Dict[str, Any] = dict(cluster_summaries)

    for cluster_id, cluster_obj in out_cluster_summaries.items():
        if not isinstance(cluster_obj, dict):
            continue

        s = cluster_obj.get("summary", "")
        if isinstance(s, str) and s.strip():
            cluster_obj["summary_de"] = translate_en_to_de(s)
        else:
            cluster_obj["summary_de"] = ""

        out_cluster_summaries[cluster_id] = cluster_obj

    data["cluster_summaries"] = out_cluster_summaries
    return MegaSummaryTranslateResponse(payload=data)
