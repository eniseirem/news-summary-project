"""
translate_en_to_de.py
=====================

Translation module for English to German text translation for output to the frontend.

Purpose
-------
Translates English text to German using MarianMT (Helsinki-NLP/opus-mt-en-de).
Designed for translating summaries and other text content to the frontend.

Processing
----------
- Uses MarianMT model with lazy loading and caching
- Chunks long text by sentence boundaries to avoid truncation
- Handles empty text gracefully
- Uses GPU if available, falls back to CPU

Notes
-----
- Model: Helsinki-NLP/opus-mt-en-de
- Max input tokens: 512 (MarianMT limit)
- Chunking: Conservative sentence-based chunking (max 1200 chars per chunk)
- Translation: Beam search with 4 beams, early stopping enabled
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple
from threading import Lock
import logging
import re

import torch
from transformers import MarianMTModel, MarianTokenizer
from transformers.tokenization_utils_base import BatchEncoding

logger = logging.getLogger(__name__)

# One model only: English -> German
_MODEL_NAME = "Helsinki-NLP/opus-mt-en-de"

_model_cache: Dict[str, Tuple[MarianMTModel, MarianTokenizer]] = {}
_model_lock = Lock()

# MarianMT typical max input length is 512 tokens
_MAX_INPUT_TOKENS = 512


def _get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _get_model() -> Tuple[MarianMTModel, MarianTokenizer]:
    if _MODEL_NAME in _model_cache:
        return _model_cache[_MODEL_NAME]

    with _model_lock:
        if _MODEL_NAME in _model_cache:
            return _model_cache[_MODEL_NAME]

        logger.info(f"[translate_de] Loading MarianMT model: {_MODEL_NAME}")
        tok = MarianTokenizer.from_pretrained(_MODEL_NAME)
        model = MarianMTModel.from_pretrained(_MODEL_NAME)

        device = _get_device()
        model.to(device)  # type: ignore[call-overload]
        model.eval()

        _model_cache[_MODEL_NAME] = (model, tok)
        return model, tok


def _chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    """
    Conservative chunking by sentence boundaries to reduce truncation risk.
    """
    if not text:
        return []

    text_norm = " ".join(text.split()).strip()
    if not text_norm:
        return []

    sentences = re.split(r"(?<=[\.!?。！？])\s+", text_norm)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []

    chunks: List[str] = []
    current = ""

    for sent in sentences:
        if not current:
            current = sent
            continue
        if len(current) + 1 + len(sent) <= max_chars:
            current = f"{current} {sent}"
        else:
            chunks.append(current)
            current = sent

    if current:
        chunks.append(current)

    return chunks


def translate_en_to_de(text: str) -> str:
    """
    Translate English text -> German using MarianMT (opus-mt-en-de).
    """
    text = text or ""
    if not text.strip():
        return text

    model, tok = _get_model()
    device = next(model.parameters()).device

    chunks = _chunk_text(text)
    if not chunks:
        return ""

    batch: BatchEncoding = tok(
        chunks,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=_MAX_INPUT_TOKENS,
    )

    input_ids = batch["input_ids"].to(device)  # type: ignore[attr-defined]
    attention_mask = batch.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)  # type: ignore[attr-defined]

    with torch.no_grad():
        generated = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            num_beams=4,
            early_stopping=True,
        )

    out_chunks = tok.batch_decode(generated, skip_special_tokens=True)
    return " ".join(c.strip() for c in out_chunks if c and c.strip())
