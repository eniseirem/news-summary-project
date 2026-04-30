"""
multilingual.py
===============

Multilingual translation module for translating articles to English.

Purpose
-------
Translates articles from multiple languages (German, French, Spanish, Italian)
to English for input to the summarization pipeline using MarianMT models. Includes translation caching for performance.

Processing
----------
- Detects article language from metadata or content
- Translates non-English articles to English
- Caches translations using MD5 hash of content
- Skips translation for English articles (early exit)
- Uses MarianMT models with lazy loading and caching

Supported Languages
-------------------
- German (de) → English
- French (fr) → English
- Spanish (es) → English
- Italian (it) → English
- English (en) → No translation needed

Notes
-----
- Translation cache: LRU-style cache with max 1000 entries
- Cache key: MD5 hash of (language:title:body)
- Max input tokens: 512 (MarianMT limit)
- Preserves original language metadata in output
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from threading import Lock
from hashlib import md5

import logging
import torch
import re

from transformers import MarianMTModel, MarianTokenizer
from transformers.tokenization_utils_base import BatchEncoding

logger = logging.getLogger(__name__)

# Translation cache: key -> translated article dict
_translation_cache: Dict[str, Dict[str, Any]] = {}
_cache_max_size = 1000  # Maximum cache entries

# ---------------------------------------------------------------------------
# MarianMT model registry & lazy loading
# ---------------------------------------------------------------------------

# Map ISO language codes to MarianMT model names (source -> English).
# Extend this dict as needed when you add more languages.
_MARIAN_MODELS: Dict[str, str] = {
    "de": "Helsinki-NLP/opus-mt-de-en",
    "fr": "Helsinki-NLP/opus-mt-fr-en",
    "es": "Helsinki-NLP/opus-mt-es-en",
    "it": "Helsinki-NLP/opus-mt-it-en",
}

# Cache: model_name -> (model, tokenizer)
_model_cache: Dict[str, Tuple[MarianMTModel, MarianTokenizer]] = {}
_model_lock = Lock()

# MarianMT typical max input length is 512 tokens (confirmed in your environment).
_MAX_INPUT_TOKENS = 512


def _get_device() -> torch.device:
    """Select compute device. Prefers GPU if available."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _normalize_lang_code(lang: str | None) -> str:
    """
    Normalize language code to a short ISO-like key used in _MARIAN_MODELS.
    Examples:
        "de", "de-DE" -> "de"
        None -> "en" (default)
    """
    if not lang:
        return "en"

    lang = lang.strip().lower()
    if not lang:
        return "en"

    # handle codes like "de-DE"
    if "-" in lang:
        lang = lang.split("-", 1)[0]

    return lang


def _get_marian_model_for_lang(lang: str) -> Tuple[MarianMTModel, MarianTokenizer]:
    """
    Lazily load and cache the MarianMT model for a given source language.
    If lang == "en", this function should not be called (we skip translation).
    """
    lang = _normalize_lang_code(lang)

    if lang not in _MARIAN_MODELS:
        raise ValueError(
            f"[multilingual] No MarianMT model configured for language '{lang}'. "
            f"Add a mapping to _MARIAN_MODELS or handle this language upstream."
        )

    model_name = _MARIAN_MODELS[lang]

    # Double-checked locking to avoid race conditions in multi-thread setups
    if model_name in _model_cache:
        return _model_cache[model_name]

    with _model_lock:
        if model_name in _model_cache:
            return _model_cache[model_name]

        logger.info(f"[multilingual] Loading MarianMT model: {model_name}")
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)

        device = _get_device()
        model.to(device)  # type: ignore[call-overload]  # Move model to device
        model.eval()

        _model_cache[model_name] = (model, tokenizer)
        return model, tokenizer


# ---------------------------------------------------------------------------
# Low-level translation helpers
# ---------------------------------------------------------------------------

def _chunk_text_for_translation(text: str, max_chars: int = 1200) -> List[str]:
    """
    Split a long text into roughly max_chars chunks, preserving punctuation.
    """
    if not text:
        return []

    # Normalize whitespace
    text_norm = " ".join(text.split()).strip()
    if not text_norm:
        return []

    # Split into sentences by punctuation + following whitespace
    sentences = re.split(r"(?<=[\.!?。！？])\s+", text_norm)

    # Remove any accidental empty segments
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
            current = current + " " + sent
        else:
            chunks.append(current)
            current = sent

    if current:
        chunks.append(current)

    return chunks


def translate_text_to_en(text: str, src_lang: str) -> str:
    """
    Translate a text into English using MarianMT, if needed.

    - If src_lang is English, returns the text unchanged.
    - If src_lang is not supported in _MARIAN_MODELS, raises ValueError.
    """
    src_lang_norm = _normalize_lang_code(src_lang)

    # Already English – no-op
    if src_lang_norm == "en":
        return text

    text = text or ""
    if not text.strip():
        return text

    model, tokenizer = _get_marian_model_for_lang(src_lang_norm)
    device = next(model.parameters()).device

    chunks = _chunk_text_for_translation(text)
    if not chunks:
        return ""

    # Batch translate chunks in one go
    batch: BatchEncoding = tokenizer(
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

    translated_chunks = tokenizer.batch_decode(generated, skip_special_tokens=True)
    return " ".join(part.strip() for part in translated_chunks if part and part.strip())


# ---------------------------------------------------------------------------
# Article-level translation
# ---------------------------------------------------------------------------

def translate_single_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate a single article into English for downstream embedding/clustering.
    Uses caching to avoid re-translating identical content.

    Output contract (per your decision):
      - Always set:
            original_language  (normalized: "en", "de", ...)
      - Always end with:
            language == "en"
      - Do NOT store original_title/original_body (keeps payload light)
      - Translate title/body ONLY if language != "en"
    """
    lang_raw = article.get("language", "en")
    lang_norm = _normalize_lang_code(lang_raw)

    title = article.get("title", "") or ""
    body = article.get("body", "") or ""

    # Early exit for English articles (no translation needed)
    if lang_norm == "en":
        out: Dict[str, Any] = dict(article)
        out["original_language"] = lang_norm
        out["language"] = "en"
        return out

    # Create cache key from content hash (title + body + language)
    cache_key = md5(f"{lang_norm}:{title}:{body}".encode()).hexdigest()
    
    # Check cache
    if cache_key in _translation_cache:
        cached = _translation_cache[cache_key].copy()
        # Preserve article ID and other metadata from current article
        cached["id"] = article.get("id", cached.get("id"))
        if "source" in article:
            cached["source"] = article["source"]
        if "published_at" in article:
            cached["published_at"] = article["published_at"]
        logger.debug(f"[multilingual] Cache hit for article id={article.get('id')}")
        return cached

    # Not in cache - translate
    translated_article: Dict[str, Any] = dict(article)
    translated_article["original_language"] = lang_norm

    # Non-English -> translate title/body into English
    try:
        translated_article["title"] = translate_text_to_en(title, src_lang=lang_norm) if title else ""
        translated_article["body"] = translate_text_to_en(body, src_lang=lang_norm) if body else ""
        translated_article["language"] = "en"
        
        # Store in cache (with size limit)
        if len(_translation_cache) >= _cache_max_size:
            # Remove oldest entry (simple FIFO - remove first key)
            first_key = next(iter(_translation_cache))
            del _translation_cache[first_key]
        _translation_cache[cache_key] = translated_article.copy()
        
        return translated_article
    except Exception as exc:
        logger.error(
            f"[multilingual] Failed to translate article id={article.get('id')} "
            f"from lang='{lang_norm}': {exc}"
        )
        raise


def translate_batch_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Batch translation of articles into English.

    Error policy:
      - If language is unsupported (ValueError), keep the article but mark translation_failed=True.
        Also attach original_language (normalized) for debugging/audit.
      - Unexpected exceptions: raise.
    """
    translated: List[Dict[str, Any]] = []

    for art in articles:
        try:
            translated.append(translate_single_article(art))
        except ValueError as e:
            logger.warning(
                f"[multilingual] Translation unsupported for article id={art.get('id')}: {e}"
            )
            art2 = dict(art)
            art2["translation_failed"] = True
            art2["original_language"] = _normalize_lang_code(art.get("language", "en"))
            translated.append(art2)
        except Exception as e:
            logger.error(
                f"[multilingual] Unexpected error while translating article "
                f"id={art.get('id')}: {e}"
            )
            raise

    return translated


# ---------------------------------------------------------------------------
# Debug / introspection helper (optional)
# ---------------------------------------------------------------------------

def get_translation_model_limits(src_lang: str) -> Dict[str, Any]:
    """
    Utility to introspect tokenizer/model limits for a given source language model.
    Useful for debugging in dev. Not used by the pipeline.

    Returns:
        dict with tokenizer.model_max_length, config.max_position_embeddings, config.max_length
    """
    src_lang_norm = _normalize_lang_code(src_lang)
    if src_lang_norm == "en":
        return {"note": "English text does not require translation in this module."}

    model, tokenizer = _get_marian_model_for_lang(src_lang_norm)
    return {
        "tokenizer.model_max_length": getattr(tokenizer, "model_max_length", None),
        "config.max_position_embeddings": getattr(model.config, "max_position_embeddings", None),
        "config.max_length": getattr(model.config, "max_length", None),
        "device": str(next(model.parameters()).device),
        "model_name": _MARIAN_MODELS.get(src_lang_norm),
    }
