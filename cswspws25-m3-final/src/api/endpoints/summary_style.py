"""
summary_style.py
=================

Plain style and format rewriting endpoint for summaries.

Intended design (per Abby + docs)
---------------------------------
- /summary_style receives an existing SUMMARY (string)
- It ONLY applies optional tone/style/format transformations to that summary
- It does NOT summarize articles or perform clustering/categorization
- writing_style and output_format are optional
- institutional is optional (maps to "institutional" tone)
- If nothing is selected (no style, no format, institutional=False), returns the summary as-is
- Supports up to 3 total combinations (requested + additional)
"""

from __future__ import annotations

from typing import List, Literal, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm_engine.tone_rewriter_llama_plain import rewrite_summary_plain


WritingStyle = Literal[
    "journalistic",
    "academic",
    "executive",
]

OutputFormat = Literal[
    "paragraph",
    "bullet_points",
    "tldr",
    "sections",
]


class StyleFormatVersionPlain(BaseModel):
    """
    A single style/format-specific rewrite of the base summary (plain, no warnings).
    """
    writing_style: Optional[str] = None
    output_format: Optional[str] = None
    rewritten_summary: str
    institutional: bool


class StyleFormatComboPlain(BaseModel):
    """
    Optional additional combination.
    Each field is optional so the frontend can choose only one dimension.
    Examples:
      {"output_format": "bullet_points"}
      {"writing_style": "academic"}
      {"writing_style": "executive", "output_format": "sections"}
    """
    writing_style: Optional[WritingStyle] = None
    output_format: Optional[OutputFormat] = None


class SummaryStyleRequest(BaseModel):
    """
    Request model for plain style/format post-processing on an existing summary.

    Notes:
    - The input summary is NOT generated here.
    - Rewrites are post-processing only.
    - No defaults are added automatically.
    - Up to 3 total combinations (requested + additional).
    """
    request_id: str
    summary: str
    writing_style: Optional[WritingStyle] = None
    output_format: Optional[OutputFormat] = None
    institutional: bool = False
    additional_combinations: Optional[List[StyleFormatComboPlain]] = None
    # Optional metadata passthrough
    article_ids: Optional[List[str]] = None


class SummaryStyleResponse(BaseModel):
    """
    Response model containing the base summary and its plain style/format variations.
    """
    request_id: str
    styled_summary: str
    writing_style: Optional[str] = None
    output_format: Optional[str] = None
    institutional: bool
    article_ids: Optional[List[str]] = None
    processed_at: str


router = APIRouter(tags=["summarization", "style"])


@router.post("/summary_style", response_model=SummaryStyleResponse)
def summary_style_endpoint(payload: SummaryStyleRequest):
    # ---- Validate summary ----
    summary = (payload.summary or "").strip()
    if not summary:
        raise HTTPException(status_code=400, detail="summary cannot be empty")

    # If nothing selected, return as-is (per spec)
    if not payload.institutional and not payload.writing_style and not payload.output_format:
        return SummaryStyleResponse(
            request_id=payload.request_id,
            styled_summary=summary,
            writing_style=None,
            output_format=None,
            institutional=False,
            article_ids=payload.article_ids,
            processed_at=datetime.utcnow().isoformat(),
        )

    # ---- Determine combinations to generate (no auto-defaults) ----
    combinations_to_generate: List[dict] = [
        {
            "writing_style": payload.writing_style,
            "output_format": payload.output_format,
        }
    ]

    if payload.additional_combinations:
        for combo in payload.additional_combinations:
            combo_tuple = (combo.writing_style, combo.output_format)
            existing_tuples = [
                (c.get("writing_style"), c.get("output_format"))
                for c in combinations_to_generate
            ]
            if combo_tuple not in existing_tuples:
                combinations_to_generate.append(
                    {"writing_style": combo.writing_style, "output_format": combo.output_format}
                )
            if len(combinations_to_generate) >= 3:
                break

    # For this endpoint's minimal doc format, we return ONE "styled_summary"
    # (the "primary" combo = first one). Additional combos are not returned
    # in the minimal schema; if you later want multiple outputs, add a new response field.
    primary_combo = combinations_to_generate[0]
    editorial_tone = "institutional" if payload.institutional else None

    styled = rewrite_summary_plain(
        text=summary,
        editorial_tone=editorial_tone,
        writing_style=primary_combo.get("writing_style"),
        output_format=primary_combo.get("output_format"),
        language="en",
    )

    return SummaryStyleResponse(
        request_id=payload.request_id,
        styled_summary=styled,
        writing_style=primary_combo.get("writing_style"),
        output_format=primary_combo.get("output_format"),
        institutional=payload.institutional,
        article_ids=payload.article_ids,
        processed_at=datetime.utcnow().isoformat(),
    )
