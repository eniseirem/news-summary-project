"""
summarizer_bart.py
========
This module implements the LLM-based summarization component using a
pre-trained BART model from Hugging Face. It provides summarization functions,
which generates summaries for cleaned article text and supports configurable 
parameters such as `min_length`, `max_length`, and `do_sample`. The model is 
loaded lazily for efficiency. This module serves as the core summarization logic 
and integrates with the pipeline and API.
"""

from typing import Union, List, Dict, Any, Optional
from transformers import pipeline
import json
from pathlib import Path


# Global pipeline instance so we only load the model once
from threading import Lock
_model_lock = Lock()
_summarization_pipeline = None


def _get_summarization_pipeline(
    model_name: str = "facebook/bart-large-cnn",
    # device: -1=CPU, 0=GPU
    device: int = -1,
):
    
    
    """
    Lazily initialize and return the Hugging Face summarization pipeline.

    Parameters
    ----------
    model_name : str
        HF model ID to use for summarization.
    device : int
        -1 for CPU, 0 for first GPU, etc.
    """
    global _summarization_pipeline

    # Only load the pipeline if it has not been created already
    if _summarization_pipeline is None:
        _summarization_pipeline = pipeline(
            task="summarization",
            model=model_name,
            tokenizer=model_name,
            device=device,    # Force CPU
            framework="pt",   # Force PyTorch
            # Prevent transformer auto-optimizations
            use_fast=False,   # Avoid fast tokenizers triggering meta loads
            torch_dtype="auto",  # prevents fp16 on CPU
            device_map=None, # disables sharding / meta tensors
        )


    return _summarization_pipeline


def summarize_text(
    text: Union[str, List[str]],
    min_length: int = 80,
    max_length: int = 150,
    do_sample: bool = False,
    model_name: str = "facebook/bart-large-cnn",
    device: int = -1,
    **generate_kwargs: Any,
) -> Union[str, List[str]]:
    """
    Summarize a single cleaned article text or a list of texts.

    This version is SAFEGUARDED against overly long inputs by truncating
    the input at the TOKEN level before calling the BART model, so we
    don't hit position embedding IndexError.

    Parameters
    ----------
    text : str | List[str]
        Input text(s), assumed to be pre-cleaned by the preprocessing module.
    min_length : int
        Minimum length of the generated summary (in tokens).
    max_length : int
        Maximum length of the generated summary (in tokens).
    do_sample : bool
        If True, use sampling (more diverse summaries).
        If False, use deterministic decoding (greedy/beam).
    model_name : str
        Hugging Face model identifier for summarization.
    device : int
        -1 for CPU, 0 for first GPU, etc.
    **generate_kwargs :
        Additional generation parameters (num_beams, temperature, top_p, etc).

    Returns
    -------
    str | List[str]
        Summary (for single string input) or list of summaries.
    """
    # Handle trivial empty input
    if isinstance(text, str):
        if not text.strip():
            return ""
    else:
        if not text:
            return []

    # Load BART summarization model / pipeline
    pipe = _get_summarization_pipeline(model_name=model_name, device=device)
    tokenizer = pipe.tokenizer

    # -------- HARD TOKEN-LIMIT SAFETY LAYER --------
    # BART (facebook/bart-large-cnn) supports up to 1024 tokens.
    # We use a slightly smaller limit as a safety margin.
    MAX_INPUT_TOKENS = 900

    def _truncate_to_tokens(s: str) -> str:
        # Encode without special tokens so we control exactly how many go in
        token_ids = tokenizer.encode(s, truncation=False, add_special_tokens=False)
        if len(token_ids) > MAX_INPUT_TOKENS:
            token_ids = token_ids[:MAX_INPUT_TOKENS]
        # Decode back to string; skip_special_tokens=True to be safe
        return tokenizer.decode(token_ids, skip_special_tokens=True)

    if isinstance(text, str):
        text = _truncate_to_tokens(text)
    else:
        text = [_truncate_to_tokens(t) for t in text]
    # ------------------------------------------------
    #input_tokens = len(tokenizer.encode(text, add_special_tokens=False)) ###New

    # Summary should not exceed input tokens
    #dynamic_max = min(max_length, int(input_tokens * 0.8))

    params: Dict[str, Any] = {
        "min_length": min_length,
        "max_length": max_length, # max_length,
        "do_sample": do_sample,
        # keep truncation=True as an extra safeguard, though we already truncated
        "truncation": True,
    }
    params.update(generate_kwargs)

    # HF pipeline supports both str and List[str]
    with _model_lock: 
        result = pipe(text, **params)

    # Result is always a list of dicts: [{"summary_text": "..."}]
    # Ensure same structure as input (string in → string out; list in → list out)
    if isinstance(text, str):
        return result[0]["summary_text"]
    else:
        return [r["summary_text"] for r in result]
    
# Chunk function
"""
This splits long text into overlapping chunks of at most 'max_words' words.
Overlap helps to keep some context between chunks
"""
def chunk_text(
    text: str,
    max_words: int = 800,
    overlap_words: int = 120 
) -> List[str]:  
    words = text.split()
    n = len(words)
    if n <= max_words:
        return [" ".join(words)]

    chunks = []
    start = 0

    while start < n:
        end = min(start + max_words, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end == n:
            break

        # move start forward but keep an overlap
        start = end - overlap_words

    return chunks 

# hierarchical summary
"""
Hierarchical summarization for long texts:
1. Chunk the text into ~max_words word chunks.
2. Summarize each chunk individually.
3. If there is more than one chunk, summarize the concatenation
of all partial summaries again to get a final mega-summary.
"""    
def hierarchical_summarize(
    text: str,
    max_words: int = 800, #150 - 250 words for each summary
    overlap_words: int = 120
) -> str:
    
    # Chunk long text
    chunks = chunk_text(text, max_words=max_words, overlap_words=overlap_words)
    print(f"Number of chunks: {len(chunks)}")

    # Summarize each chunk
    partial_summaries = []
    for chunk in chunks:
        partial = summarize_text(chunk, min_length=150, max_length=250,
        )
        partial_summaries.append(partial)

    # If we have only one chunk, we’re done
    if len(partial_summaries) == 1:
        return partial_summaries[0]
    
    # If more, summarize the summaries
    combined = " ".join(partial_summaries)
    final_summary = summarize_text(combined, min_length=200, max_length=320,) 
    return final_summary      

def hierarchical_summarize_summaries(
    summaries: List[str],
    max_words: int = 800,
    overlap_words: int = 120,
    final_min_length: int = 250,
    final_max_length: int = 450,
) -> str:
    if not summaries:
        return ""

    combined = " ".join(summaries)

    # Chunk the combined summaries by words (to stay under BART's input limit)
    chunks = chunk_text(combined, max_words=max_words, overlap_words=overlap_words)

    partial = []
    for ch in chunks:
        s = summarize_text(ch)  # 30–120 tokens each
        partial.append(s)

    # If only one chunk, we're done
    if len(partial) == 1:
        return partial[0]

    # Summarize the summaries of summaries
    final_text = " ".join(partial)
    mega = summarize_text(
        final_text,
        min_length=final_min_length,
        max_length=final_max_length,
    )
    return mega

# New mega summary

"""
- Summarize each article individually into a short 1-2 sentence summary.
- Concatenate those mini-summaries.
- Summarize again to produce a balanced mega-summary.

This would work around BART's token limitations.
"""

def mega_summary(
    article_summaries: List[str],
    per_article_min: int = 60, #40 
    per_article_max: int = 150, #60
    final_min: int = 250,
    final_max: int = 450,
) -> str:

    if not article_summaries:
        return ""

    mini_summaries = []

    # each article -> short summary
    for s in article_summaries:
        short = summarize_text(
            s,
            min_length=per_article_min,
            max_length=per_article_max,
        )
        mini_summaries.append(short)

    # combine all mini summaries
    combined = " ".join(mini_summaries)

    # paraphrase/mega-summarize the combined text
    final = summarize_text(
        combined,
        min_length=final_min,
        max_length=final_max,
    )

    return final

"""
- Summarize each article into one short sentence (20-40 tokens)
- Combine/Concatenate all short summaries
"""

def new_mega_summary(
    article_summaries: List[str],
    per_article_min: int = 60,
    per_article_max: int = 150,
) -> str:

    if not article_summaries:
        return ""

    mini_summaries = []

    # each article -> short summary
    for s in article_summaries:
        short = summarize_text(
             s,
             min_length=per_article_min,
             max_length=per_article_max,
        )
    
        mini_summaries.append(short)

    # combine all mini summaries
    combined = " ".join(mini_summaries)

    return combined


    
