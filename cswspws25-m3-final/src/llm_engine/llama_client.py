"""
llama_client.py
================
Low-level client for calling the LLaMA 3 model via Ollama.

Purpose
-------
This module provides a minimal, well-defined interface between the
LLM pipeline and the Ollama inference backend. It is responsible for:

- Loading the LLaMA configuration from `src/models/llm_configs/llama3.yaml`
- Selecting the active model variant (3B for dev, 8B for prod)
- Exposing read-only accessors such as:
    * get_model_name()
    * get_context_tokens()
    * get_generation_settings()
    * get_length_control_config()
- Sending deterministic generation requests to Ollama's `/api/generate`
- Hiding all HTTP / JSON details from the rest of the codebase
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import os
import requests
import yaml


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

LLAMA_CONFIG_ENV = "LLAMA_CONFIG_PATH"


def _default_config_path() -> Path:
    here = Path(__file__).resolve()
    src_root = here.parents[1]  # .../src
    return src_root / "models" / "llm_configs" / "llama3.yaml"


@lru_cache(maxsize=1)
def load_llama_config() -> Dict[str, Any]:
    """
    Load the LLaMA configuration from YAML.

    - Reads from LLAMA_CONFIG_PATH env var if set.
    - Falls back to the default path under src/models/llm_configs/llama3.yaml.
    - Uses LRU cache to avoid re-reading the file on every call.
    """
    cfg_path_str = os.getenv(LLAMA_CONFIG_ENV)
    if cfg_path_str:
        cfg_path = Path(cfg_path_str).resolve()
    else:
        cfg_path = _default_config_path()

    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"[llama_client] Could not find LLaMA config at: {cfg_path}"
        )

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError(
            f"[llama_client] Invalid config format in {cfg_path}; expected a YAML mapping."
        )

    return cfg


# ---------------------------------------------------------------------------
# Public accessors for model configuration
# ---------------------------------------------------------------------------

def get_model_name() -> str:
    """
    Return the active Ollama model name, e.g. 'llama3.2:3b' or 'llama3.1:8b'.

    The active variant is determined by:
    - config['default_variant'] in llama3.yaml
    - config['variants'][default_variant]['model_name']
    """
    cfg = load_llama_config()
    variants = cfg.get("variants", {})
    default_variant = cfg.get("default_variant")

    if default_variant not in variants:
        raise KeyError(
            f"[llama_client] default_variant='{default_variant}' "
            f"not found under 'variants' in llama3.yaml."
        )

    model_name = variants[default_variant].get("model_name")
    if not model_name:
        raise KeyError(
            f"[llama_client] 'model_name' missing for variant '{default_variant}'."
        )

    return str(model_name)


def get_context_tokens() -> int:
    """
    Return the approximate context window (in tokens) for the active model.

    This value is only a *hint* for the summarizer and is used to decide:
    - Whether we can summarize the whole text in a single call
    - Or whether we need to chunk and perform hierarchical summarization
    """
    cfg = load_llama_config()
    variants = cfg.get("variants", {})
    default_variant = cfg.get("default_variant")

    variant_cfg = variants.get(default_variant, {})
    ctx = variant_cfg.get("context_tokens")

    if ctx is None:
        # Reasonable fallback if not specified in YAML
        return 128000

    return int(ctx)


def get_generation_settings() -> Dict[str, Any]:
    """
    Return the base generation settings from the configuration.

    Example keys:
        - temperature
        - top_p
        - top_k
        - seed

    Dynamic length control is stored under:
        generation.length_control
    and accessed via get_length_control_config().
    """
    cfg = load_llama_config()
    gen_cfg = cfg.get("generation", {})
    if not isinstance(gen_cfg, dict):
        gen_cfg = {}

    return gen_cfg


def get_length_control_config() -> Dict[str, float]:
    """
    Return dynamic length control settings for summaries.

    Config path:
        generation.length_control

    Expected keys:
        - per_cluster_words: int
        - max_words: int
        - tokens_per_word: float
    """
    cfg = load_llama_config()
    gen_cfg = cfg.get("generation", {})
    lc_cfg = gen_cfg.get("length_control", {})

    if not isinstance(lc_cfg, dict):
        lc_cfg = {}

    return {
        "per_cluster_words": float(lc_cfg.get("per_cluster_words", 150)),
        "max_words": float(lc_cfg.get("max_words", 1200)),
        "tokens_per_word": float(lc_cfg.get("tokens_per_word", 1.3)),
    }


# ---------------------------------------------------------------------------
# Low-level HTTP call to Ollama
# ---------------------------------------------------------------------------

def _get_ollama_base_url() -> str:
    """
    Resolve the Ollama base URL from environment variables.

    Priority:
    1. OLLAMA_HOST (used in docker-compose)
    2. OLLAMA_BASE_URL (fallback for older configs)
    3. Default: http://localhost:11434
    """
    return (
        os.getenv("OLLAMA_HOST")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    )


def generate_raw(
    prompt: str,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
) -> str:
    """
    Send a deterministic generation request to Ollama's /api/generate endpoint.

    Parameters
    ----------
    prompt : str
        Full text prompt to send to LLaMA.
    max_tokens : int, optional
        Maximum number of tokens to generate. If None, a sensible default (512) is used.
    timeout : int, optional
        Timeout (in seconds) for the HTTP request. Defaults to 1800 seconds (30 minutes) for large batches.

    Returns
    -------
    str
        The generated text from LLaMA (no post-processing applied).
    """
    gen_cfg = get_generation_settings()

    if max_tokens is None:
        max_tokens = 512

    options: Dict[str, Any] = {
        "temperature": float(gen_cfg.get("temperature", 0.0)),
        "top_p": float(gen_cfg.get("top_p", 1.0)),
        "top_k": int(gen_cfg.get("top_k", 0)),
        "num_predict": int(max_tokens),
        "seed": int(gen_cfg.get("seed", 42)),
    }

    base_url = _get_ollama_base_url()
    model_name = get_model_name()
    # Increased timeout for large batches: 300s → 1800s (30 minutes)
    request_timeout = timeout or 1800

    print(f"[LLAMA_CLIENT] Sending request to {base_url}/api/generate")
    print(f"[LLAMA_CLIENT] Model: {model_name}, Prompt length: {len(prompt)} chars, Max tokens: {max_tokens}, Timeout: {request_timeout}s")
    
    # First, verify Ollama is responding
    try:
        health_check = requests.get(f"{base_url}/api/tags", timeout=5)
        if health_check.status_code != 200:
            raise RuntimeError(f"Ollama health check failed: {health_check.status_code}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot connect to Ollama at {base_url}. Is Ollama running? Try: ollama serve")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Ollama at {base_url} is not responding. It may be stuck or overloaded.")
    
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "options": options,
                "stream": False,
            },
            timeout=request_timeout,
        )
        print(f"[LLAMA_CLIENT] Response received: status={response.status_code}")
    except requests.exceptions.Timeout:
        print(f"[LLAMA_CLIENT] ERROR: Request timed out after {request_timeout} seconds")
        print(f"[LLAMA_CLIENT] Ollama may be stuck. Try restarting Ollama.")
        raise
    except requests.exceptions.ConnectionError as e:
        print(f"[LLAMA_CLIENT] ERROR: Cannot connect to Ollama at {base_url}. Is Ollama running?")
        raise
    except Exception as e:
        print(f"[LLAMA_CLIENT] ERROR: Unexpected error: {e}")
        raise

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"[llama_client] Ollama /api/generate request failed: {exc}"
        ) from exc

    data = response.json()
    text = data.get("response", "")

    if not isinstance(text, str):
        raise ValueError(
            f"[llama_client] Unexpected response format from Ollama: {data}"
        )

    return text
