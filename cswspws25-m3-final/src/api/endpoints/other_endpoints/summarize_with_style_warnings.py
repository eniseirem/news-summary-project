"""
summarize_with_style.py
=======================

Style and format rewriting endpoint for summaries.

Purpose
-------
This endpoint generates a single base summary from a batch of articles and
then rewrites that summary using different writing styles and output formats using LLaMA.

This endpoint is intentionally separated from clustering and category logic.
It operates purely as a **post-processing layer** on top of summarization.

Design Notes
------------
- No clustering is performed
- No topic categorization is performed
- No length control beyond the base summarization
- All style/format rewrites are derived from the SAME base summary
- Output language is always English

This endpoint is primarily intended for:
- Frontend writing style selection (radio buttons / toggles)
- Output format selection (paragraph, bullet points, etc.)
- A/B comparison of writing styles and formats
- UI previews without re-running summarization
"""

from typing import List, Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from api.schemas import Article
from llm_engine.model_loader import get_summarizer_backend
from llm_engine.tone_rewriter_llama import rewrite_summary_with_warnings


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


class StyleFormatVersion(BaseModel):
    """
    A single style/format-specific rewrite of the base summary.
    """
    writing_style: str
    output_format: str
    rewritten_summary: str
    institutional: bool
    warnings: List[str] = []


class SummarizeWithStyleRequest(BaseModel):
    """
    Request model for style and format-based summarization.

    Notes:
    - Articles are summarized ONCE
    - Style/format rewrites are applied as post-processing
    - If additional_combinations are not provided, default combinations are generated
    """
    writing_style: WritingStyle = "journalistic"
    output_format: OutputFormat = "paragraph"
    institutional: bool = False
    articles: List[Article]
    additional_combinations: Optional[List[dict]] = None
    """
    Optional list of additional style/format combinations to generate.
    Format: [{"writing_style": "academic", "output_format": "bullet_points"}, ...]
    Maximum of 3 total combinations (requested + additional).
    """


class SummarizeWithStyleResponse(BaseModel):
    """
    Response model containing the base summary and its style/format variations.
    """
    article_ids: List[str]  # List of article IDs that were summarized
    article_count: int
    initial_summary: str
    style_format_versions: List[StyleFormatVersion]


router = APIRouter(tags=["summarization", "style"])


@router.post("/summarize_with_style", response_model=SummarizeWithStyleResponse)
def summarize_with_style_endpoint(payload: SummarizeWithStyleRequest):
    """
    Generate a base summary and rewrite it using different writing styles and output formats.

    Processing Steps
    ----------------
    1. Concatenate all article texts
    2. Generate a single base summary using the LLM summarizer
    3. Rewrite the base summary using one or more writing style/output format combinations

    Style/Format Handling
    ---------------------
    - The requested writing_style and output_format combination is always generated
    - If additional_combinations are provided, they are included
    - Otherwise, up to two default combinations are added:
        * journalistic + paragraph
        * executive + bullet_points
    - Maximum of three style/format versions per request

    Constraints
    -----------
    - No clustering
    - No category or mega summaries
    - No hierarchical summarization
    - No translation (English only)

    Intended Usage
    --------------
    - Frontend style and format selection
    - Editorial style previews
    - Post-processing of summaries without recomputation

    Parameters
    ----------
    payload : SummarizeWithStyleRequest
        Request containing articles and desired writing style/output format.

    Returns
    -------
    SummarizeWithStyleResponse
        Base summary and multiple style/format-specific rewrites.
    """

    # ---- Combine article texts ----
    article_texts: List[str] = []
    for art in payload.articles:
        title_prefix = f"{art.title}. " if art.title else ""
        body_text = art.body or ""
        article_texts.append(title_prefix + body_text)

    combined_text = "\n\n".join(article_texts)

    # ---- Generate base summary ----
    backend = get_summarizer_backend()
    initial_summary = backend.summarize(
        text=combined_text,
        summary_length="medium",
        language="en",
    )

    # ---- Determine style/format combinations to generate ----
    combinations_to_generate: List[dict] = [
        {
            "writing_style": payload.writing_style,
            "output_format": payload.output_format,
        }
    ]

    if payload.additional_combinations:
        for combo in payload.additional_combinations:
            # Validate combination
            if not isinstance(combo, dict):
                continue
            writing_style = combo.get("writing_style")
            output_format = combo.get("output_format")
            
            if writing_style not in ["journalistic", "academic", "executive"]:
                continue
            if output_format not in ["paragraph", "bullet_points", "tldr", "sections"]:
                continue
            
            # Check if combination already exists
            combo_tuple = (writing_style, output_format)
            existing_tuples = [
                (c["writing_style"], c["output_format"]) for c in combinations_to_generate
            ]
            if combo_tuple not in existing_tuples:
                combinations_to_generate.append(combo)
    else:
        # Add default combinations
        default_combinations = [
            {"writing_style": "journalistic", "output_format": "paragraph"},
            {"writing_style": "executive", "output_format": "bullet_points"},
        ]
        for default_combo in default_combinations:
            combo_tuple = (
                default_combo["writing_style"],
                default_combo["output_format"],
            )
            existing_tuples = [
                (c["writing_style"], c["output_format"])
                for c in combinations_to_generate
            ]
            if combo_tuple not in existing_tuples:
                combinations_to_generate.append(default_combo)
            if len(combinations_to_generate) >= 3:
                break

    # ---- editorial tone mapping (once per request) ----
    editorial_tone = "institutional" if payload.institutional else "neutral"

    # ---- Generate style/format rewrites ----
    style_format_versions: List[StyleFormatVersion] = []

    for combo in combinations_to_generate:
        rewrite_res = rewrite_summary_with_warnings(
            text=initial_summary,
            editorial_tone=editorial_tone,
            writing_style=combo["writing_style"],
            output_format=combo["output_format"],
            language="en",
            enable_llm_validation=True,
        )

        rewritten_summary = rewrite_res["text"]
        version_warnings = rewrite_res.get("soft_warnings", []) or []

        style_format_versions.append(
            StyleFormatVersion(
                writing_style=combo["writing_style"],
                output_format=combo["output_format"],
                rewritten_summary=rewritten_summary,
                institutional=payload.institutional,
                warnings=version_warnings,
            )
        )

    return SummarizeWithStyleResponse(
        article_ids=[art.id for art in payload.articles],
        article_count=len(payload.articles),
        initial_summary=initial_summary,
        style_format_versions=style_format_versions,
    )

