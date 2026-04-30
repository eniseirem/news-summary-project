"""
model_loader.py
================

Backend selector and factory for summarization models.

Purpose
-------
Provides a unified interface for selecting and using summarization backends.
Supports both BART (legacy) and LLaMA 3 (primary) backends with automatic
selection based on environment variables.

Backend Selection
----------------
Priority order:
1. LLM_BACKEND environment variable
2. SUMMARY_BACKEND environment variable
3. Default: "llama"

Supported Backends
------------------
- BART (legacy): facebook/bart-large-cnn via Hugging Face
- LLaMA 3 (primary): Via Ollama local inference

Backend Interface
-----------------
All backends implement the SummarizerBackend protocol:
- summarize(text, summary_length, language) -> str
- get_model_name() -> str

LLaMA Backend Features
----------------------
- Cluster-level summarization
- Category-level summarization
- Mega summary generation
- Configurable via llama3.yaml

Notes
-----
- BART backend uses hierarchical summarization (800 words max)
- LLaMA backend uses Ollama API for inference
- Backend selection is done at runtime, not import time
"""

from __future__ import annotations

from typing import Literal, Protocol
import os

# Legacy BART-based summarization module (Milestone 1)
from . import summarizer_bart

# New LLaMA-based summarization module (Milestone 2)
from . import summarizer_llama
from . import llama_client


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SummaryLength = Literal["short", "medium", "long"]


# ---------------------------------------------------------------------------
# Protocol for summarization backends
# ---------------------------------------------------------------------------

class SummarizerBackend(Protocol):
    """Protocol that all summarization backends must implement."""
    
    def summarize(
        self,
        text: str,
        summary_length: SummaryLength = "medium",
        language: str = "en",
    ) -> str:
        """Summarize the given text."""
        ...
    
    def get_model_name(self) -> str:
        """Return the model name used by this backend."""
        ...


# ---------------------------------------------------------------------------
# BART backend implementation (legacy)
# ---------------------------------------------------------------------------

class BartBackend:
    """Summarization backend using the legacy BART model."""

    # Underlying model name (used in API responses)
    model_name: str = "bart-large-cnn"

    def summarize(
        self,
        text: str,
        summary_length: SummaryLength = "medium",
        language: str = "en",
    ) -> str:
        """
        Summarize the given text using the existing hierarchical BART logic.
        summary_length and language are kept only for interface compatibility.
        """
        if not text.strip():
            return ""

        return summarizer_bart.hierarchical_summarize(
            text,
            max_words=800,
            overlap_words=120,
        )

    def get_model_name(self) -> str:
        return self.model_name


# ---------------------------------------------------------------------------
# LLaMA backend implementation (primary)
# ---------------------------------------------------------------------------

class LlamaBackend:
    """Summarization backend using LLaMA 3 via Ollama."""

    # ------------------------------------------------------------------
    # legacy single-call summarize() for compatibility
    # ------------------------------------------------------------------
    def summarize(
        self,
        text: str,
        summary_length: SummaryLength = "medium",  # only for legacy compatibility
        language: str = "en",
    ) -> str:
        
        if not text.strip():
            return ""

        return summarizer_llama.summarize_cluster_with_llama(
            text=text,
            language=language,
        )

    # ------------------------------------------------------------------
    # 1) Cluster-level summary
    # ------------------------------------------------------------------
    def summarize_cluster(
        self,
        text: str,
        language: str = "en",
    ) -> str:
        """
        Summarize one cluster (all articles on the same topic).

        text: concatenated raw articles for this cluster.
        """
        if not text.strip():
            return ""

        return summarizer_llama.summarize_cluster_with_llama(
            text=text,
            language=language,
        )

    # ------------------------------------------------------------------
    # 2) Category-level summary
    # ------------------------------------------------------------------
    def summarize_category(
        self,
        text: str,
        num_clusters: int,
        language: str = "en",
    ) -> str:
        """
        Summarize one category based on all its cluster summaries.

        text:         concatenation of all cluster summaries in this category
        num_clusters: number of clusters in this category
        """
        if not text.strip():
            return ""

        return summarizer_llama.summarize_category_with_llama(
            text=text,
            num_clusters=num_clusters,
            language=language,
        )

    # ------------------------------------------------------------------
    # 3) MEGA summary
    # ------------------------------------------------------------------
    def summarize_mega(
        self,
        text: str,
        total_clusters: int,
        language: str = "en",
    ) -> str:
        """
        Global MEGA summary across all categories and all clusters.

        text:           concatenation of all cluster summaries across categories
        total_clusters: total number of clusters in the whole briefing
        """
        if not text.strip():
            return ""

        return summarizer_llama.summarize_mega_with_llama(
            text=text,
            total_clusters=total_clusters,
            language=language,
        )

    # ------------------------------------------------------------------
    # Model name getter (for API responses)
    # ------------------------------------------------------------------
    def get_model_name(self) -> str:
        """Return the active Ollama model name."""
        return llama_client.get_model_name()

# ---------------------------------------------------------------------------
# Backend selector
# ---------------------------------------------------------------------------

def _resolve_backend_name() -> str:
    """
    Resolve which backend to use from environment variables.

    Priority:
    1. LLM_BACKEND
    2. SUMMARY_BACKEND
    3. Default: "llama"

    Allowed values (case-insensitive):
    - "bart"
    - "llama"
    """
    env_backend = (
        os.getenv("LLM_BACKEND")
        or os.getenv("SUMMARY_BACKEND")
        or "llama"
    )
    return env_backend.strip().lower()


def get_summarizer_backend() -> SummarizerBackend:
    """
    Factory function that returns the active summarization backend.

    Returns
    -------
    SummarizerBackend
        Either a BartBackend or LlamaBackend instance, depending on env config.
    """
    backend_name = _resolve_backend_name()

    if backend_name == "bart":
        return BartBackend()

    # Default and recommended backend: LLaMA 3 via Ollama
    if backend_name == "llama":
        return LlamaBackend()

    # Fallback: unknown name → use LLaMA
    return LlamaBackend()
