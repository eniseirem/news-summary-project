"""
summarize_batch.py
==================

Batch (non-clustered) multi-article summarization endpoint.

Purpose
-------
This endpoint performs a simple, direct summarization over a batch of
articles by concatenating their content and sending it to the configured
LLM summarization backend.

This is the lightest-weight summarization path in the system and is intended
for:
- Small article sets
- Fast summaries
- Situations where topic clustering is unnecessary

Design Notes
------------
- No clustering is performed
- No hierarchical summarization
- No tone / style / format rewriting
- No source-based post-processing
- All articles are assumed to already be filtered upstream
- Output language is always English

This endpoint exists alongside cluster-based endpoints and should be used
only when topic separation is not required.
"""

from llm_engine.model_loader import get_summarizer_backend
from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import List
from datetime import datetime
from api.schemas import Article


class SummarizeBatchRequest(BaseModel):
    request_id: str
    filters_used: dict
    articles: List[Article]


class SummarizeBatchResponse(BaseModel):
    request_id: str
    summary_type: str = "batch_summary"
    filters_used: dict
    article_count: int
    article_ids: List[str]  # List of article IDs that were summarized
    model: str
    language: str
    final_summary: str
    processed_at: str


router = APIRouter(tags=["summarization", "batch"])


@router.post("/summarize_batch", response_model=SummarizeBatchResponse)
def summarize_batch(payload: SummarizeBatchRequest, response: Response):
    """
    Generate a single summary from multiple articles without clustering.

    Processing Steps
    ----------------
    1. Concatenate article titles and bodies into one text block
    2. Send combined text to the active LLM summarization backend
    3. Return the generated summary with metadata

    Constraints
    -----------
    - No topic clustering
    - No hierarchical chunking
    - No tone or style rewriting
    - No source attribution or post-processing
    - Input articles must already be filtered and deduplicated upstream

    Intended Usage
    --------------
    - Small article batches
    - Quick digests
    - n8n workflows where clustering adds no value
    - Fallback summarization path

    Parameters
    ----------
    payload : SummarizeBatchRequest
        Request containing article list and metadata.

    Returns
    -------
    SummarizeBatchResponse
        Final summary and metadata.
    """
    
    # Send immediate acknowledgment headers to keep connection alive
    response.headers["X-Request-Id"] = payload.request_id
    response.headers["X-Status"] = "processing"
    response.headers["Connection"] = "keep-alive"

    # ---- Collect & merge article texts ----
    article_texts: List[str] = []
    for art in payload.articles:
        title_prefix = f"{art.title}. " if art.title else ""
        body_text = art.body or ""
        article_texts.append(title_prefix + body_text)

    combined_text = "\n\n".join(article_texts)

    # ---- Choose summarizer backend ----
    backend = get_summarizer_backend()

    # ---- Summarization ----
    final_summary = backend.summarize(
        text=combined_text,
        language="en",
    )

    # ---- Discover model name ----
    try:
        model_name = backend.get_model_name()
    except (AttributeError, Exception):
        # Fallback if get_model_name doesn't exist or fails
        model_name = getattr(backend, "model_name", "llm-backend")

    # ---- Return response ----
    return {
        "request_id": payload.request_id,
        "summary_type": "batch_summary",
        "filters_used": payload.filters_used,
        "article_count": len(payload.articles),
        "article_ids": [art.id for art in payload.articles],  # Explicit article_ids list
        "language": "en",
        "model": model_name,
        "final_summary": final_summary,
        "processed_at": datetime.utcnow().isoformat(),
    }
