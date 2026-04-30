"""
main.py
========
Initializes FastAPI for the LLM Processing Pipeline.

Purpose
-------
This service exposes several summarization-related endpoints, including:

- /summarize_batch
    * Accepts a batch of articles from n8n or the crawler
    * Cleans HTML/content
    * Performs language detection + optional translation
    * Calls the LLM backend (BART or LLaMA via model_loader)
    * Returns a structured JSON multi-article summary

- /hierarchical_summary
    * Summarizes each article individually, then merges summaries

- /mega_summary, /mega_summary_v2
    * Experimental mega-summarization strategies for Milestone 1


Milestone 2 update
------------------
The /summarize_batch endpoint no longer calls the BART summarizer directly.
Instead, it uses the unified model_loader interface so that the backend
can be switched between:
    - BART (legacy baseline)
    - LLaMA (Ollama-based, deterministic)

Other endpoints still use the legacy BART-based summarizer for now
to minimize changes and keep behavior stable while LLaMA integration
is being developed.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime
import re
import time

# Initialize FastAPI app
app = FastAPI(
    title="LLM Processing Pipeline API",
    # Increased timeout for large batch processing
    # Note: uvicorn timeout should also be increased when starting the server
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to add keep-alive headers and handle long-running requests
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add headers to prevent connection timeouts for long-running requests."""
    start_time = time.time()
    
    # Add headers to keep connection alive
    response = await call_next(request)
    
    # Add keep-alive and timeout headers
    response.headers["Connection"] = "keep-alive"
    response.headers["Keep-Alive"] = "timeout=1800, max=1000"
    response.headers["X-Request-Id"] = getattr(request.state, "request_id", "unknown")
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Health check endpoint - responds immediately
@app.get("/health")
async def health_check():
    """Health check endpoint that responds immediately."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "LLM Processing Pipeline API"
    }

# ------------------------------
# Imports from internal modules
# -----------------------------
from llm_engine.summarizer_bart import (
    hierarchical_summarize,
    mega_summary as create_mega,
    new_mega_summary,
)

# New unified model loader (BART <-> LLaMA adapter)
from llm_engine.model_loader import get_summarizer_backend

# Batch summarization
from api.endpoints.summarize_batch import router as summarize_batch_router

# Clustering
from api.endpoints.cluster_create import router as cluster_create_router
from api.endpoints.cluster_summarize import router as cluster_summarize_router
from api.endpoints.cluster_update import router as cluster_update_router
from api.endpoints.cluster_maintenance import router as cluster_maintenance_router
from api.endpoints.cluster_stats import router as cluster_stats_router
from api.endpoints.cluster_summary import router as cluster_summary_router


# Mega summarization
from api.endpoints.mega_summarize import router as mega_summarize_router

# Labeling / extraction
from api.endpoints.topic_label import router as topic_label_router
from api.endpoints.category_label import router as category_label_router
from api.endpoints.keyword_extract import router as keyword_extract_router

# Style / tone rewriting 
from api.endpoints.summary_style import router as summary_style_router

# Translation
from api.endpoints.translate_cluster_summary import router as translate_cluster_summary_router
from api.endpoints.translate_mega_summary import router as translate_mega_summary_router

# Evaluation
from api.endpoints.evaluate_cluster import router as evaluate_cluster_router
from api.endpoints.evaluate_mega import router as evaluate_mega_router

# ------------------------------
# Include routers
# ------------------------------
app.include_router(summarize_batch_router)

# clustering
app.include_router(cluster_create_router)
app.include_router(cluster_summarize_router)
app.include_router(cluster_update_router)
app.include_router(cluster_maintenance_router)
app.include_router(cluster_stats_router)
app.include_router(cluster_summary_router)

# mega
app.include_router(mega_summarize_router)

# labeling / extraction
app.include_router(topic_label_router)
app.include_router(category_label_router)
app.include_router(keyword_extract_router)

# style
app.include_router(summary_style_router)

# translation
app.include_router(translate_cluster_summary_router)
app.include_router(translate_mega_summary_router)

# evaluation
app.include_router(evaluate_cluster_router)
app.include_router(evaluate_mega_router)


# ------------------------------
# Pydantic Models
# ------------------------------
# Article model moved to api.schemas to avoid circular imports
from api.schemas import Article


class BatchRequest(BaseModel):
    request_id: str
    filters_used: dict
    articles: List[Article]
    writing_style: Optional[
        Literal[
            "journalistic",
            "academic",
            "executive"
        ]
    ] = "journalistic"
    output_format: Optional[
        Literal[
            "paragraph",
            "bullet_points",
            "tldr",
            "sections"
        ]
    ] = "paragraph"


# ------------------------------
# NOTE: /summarize_batch endpoint is now handled by summarize_batch_router
# (see app.include_router(summarize_batch_router) above)
# The duplicate endpoint that was here has been removed to avoid route conflicts.
# ------------------------------
# Please don't change below! Legacy BART-based Endpoints (Milestone 1 compatibility)
# ------------------------------

@app.post("/hierarchical_summary")
def hierarchical_summary_endpoint(payload: BatchRequest):
    """
    Accepts the SAME structure as summarize_batch but:
    - Summarizes each article individually (using legacy BART backend)
    - Combines those summaries into one mega-summary

    This is equivalent to:
    run_summarizer_demo() in API form.

    NOTE:
    -----
    This endpoint still uses the original BART-based summarizer to keep
    behavior stable while LLaMA integration is rolled out incrementally.
    """
    per_article_summaries: List[str] = []

    for art in payload.articles:
        # Use article body directly (crawler provides clean data)
        text = art.body or ""
        if art.title:
            text = f"{art.title}. {text}".strip()
            
        summary = hierarchical_summarize(text)
        per_article_summaries.append(summary)

    mega = create_mega(
        per_article_summaries,
        per_article_min=60,
        per_article_max=150,
        final_min=250,
        final_max=450,
    )

    return {
        "request_id": payload.request_id,
        "summary_type": "mega_summary",
        "filters_used": payload.filters_used or {},
        "article_count": len(payload.articles),
        "model": "bart-large-cnn",  # still using BART here
        "language": "en",
        "final_summary": mega,
        "processed_at": datetime.utcnow().isoformat(),
    }


# ------------------------------
# Mega combined summary endpoint
# ------------------------------

@app.post("/mega_summary")
def mega_summary_endpoint(payload: BatchRequest):
    """
    Improved mega summary:
    short per-article summaries → mega summary.

    NOTE:
    -----
    This endpoint currently uses the BART-based hierarchical_summarize
    and mega_summary helper (legacy Milestone 1 behavior).
    """
    per_article_summaries: List[str] = []

    for art in payload.articles:
        # Use article body directly (crawler provides clean data)
        text = art.body or ""
        if art.title:
            text = f"{art.title}. {text}".strip()

        short_summary = hierarchical_summarize(text)
        per_article_summaries.append(short_summary)

    mega = create_mega(
        per_article_summaries,
        per_article_min=60,
        per_article_max=150,
        final_min=250,
        final_max=450,
    )

    return {
        "request_id": payload.request_id,
        "summary_type": "mega_summary",
        "filters_used": payload.filters_used or {},
        "article_count": len(payload.articles),
        "model": "bart-large-cnn",
        "language": "en",
        "final_summary": mega,
        "processed_at": datetime.utcnow().isoformat(),
    }


@app.post("/mega_summary_v2")
def mega_summary_v2_endpoint(payload: BatchRequest):
    """
    Variant of mega summary endpoint.

    Steps:
    - Summarize each article individually (short summary)
    - Concatenate all short summaries into a long text
    - Return the concatenation as the "new mega summary"

    NOTE:
    -----
    This endpoint is also still using the legacy BART-based summarizer.
    """
    per_article_summaries: List[str] = []

    for art in payload.articles:
        # Use article body directly (crawler provides clean data)
        text = art.body or ""
        if art.title:
            text = f"{art.title}. {text}".strip()

        short_summary = hierarchical_summarize(text)
        per_article_summaries.append(short_summary)

    final_output = new_mega_summary(
        per_article_summaries,
        per_article_min=40,
        per_article_max=60,
    )

    return {
        "request_id": payload.request_id,
        "summary_type": "new_mega_summary",
        "filters_used": payload.filters_used or {},
        "article_count": len(payload.articles),
        "model": "bart-large-cnn",
        "language": "en",
        "final_summary": final_output,
        "processed_at": datetime.utcnow().isoformat(),
    }

