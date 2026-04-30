"""
summarizer_llama.py
===================

LLaMA-based summarization module using Ollama for inference.

Purpose
-------
Provides summarization functions using LLaMA 3 via Ollama API. Supports
hierarchical summarization for long texts and batch processing for multiple
articles.

Features
--------
- Cluster-level summarization (multiple articles on same topic)
- Category-level summarization (multiple cluster summaries)
- Mega summary generation (all clusters across categories)
- Article-level batch summarization (individual 100-word summaries)
- Hierarchical chunking for texts exceeding context window
- Configurable length control via llama3.yaml

Processing
----------
- Uses LLaMA 3 model via Ollama (local inference)
- Hierarchical chunking for texts > context window
- Token-based length control (words → tokens conversion)
- Soft truncation to respect max word limits
- Batch processing with parallel execution support

Configuration
-------------
- Model config: src/models/llm_configs/llama3.yaml
- Length control: per_cluster_words, max_words, tokens_per_word
- Context tokens: 128,000 (default, configurable)

Notes
-----
- Requires Ollama service running locally
- Model selection: llama3:3b (dev) or llama3:8b (prod)
- Supports English and other languages (via language parameter)
- Handles empty text gracefully
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any

from . import llama_client


# ---------------------------------------------------------------------------
# Length / token utilities
# ---------------------------------------------------------------------------

def _get_length_config():
    cfg = llama_client.get_length_control_config()
    # configurable
    per_cluster_words = int(cfg.get("per_cluster_words", 150))
    max_words = int(cfg.get("max_words", 1200))
    tokens_per_word = float(cfg.get("tokens_per_word", 1.3))
    return per_cluster_words, max_words, tokens_per_word


def _words_to_tokens(words: int, margin: float = 1.3) -> int:
    _, _, tokens_per_word = _get_length_config()
    return int(words * tokens_per_word * margin)


def _approx_tokens(text: str) -> int:
    _, _, tokens_per_word = _get_length_config()
    word_count = len(text.split())
    return int(word_count * tokens_per_word)


def _needs_hierarchical(text: str) -> bool:
    if not text.strip():
        return False
    approx_tok = _approx_tokens(text)
    ctx = llama_client.get_context_tokens()  # e.g. 128_000
    return approx_tok > ctx


def _soft_truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


# ---------------------------------------------------------------------------
# Chunking logic for hierarchical safeguard
# ---------------------------------------------------------------------------

def _chunk_text(
    text: str,
    max_words: Optional[int] = None,
    overlap_words: int = 200,
    aggressive: bool = False,  # Use smaller chunks for very large inputs
) -> List[str]:
    words = text.split()
    n = len(words)
    if n == 0:
        return [""]

    if max_words is None:
        ctx_tokens = llama_client.get_context_tokens()
        _, _, tokens_per_word = _get_length_config()
        # Use smaller chunks (30-40% of context) for aggressive mode to avoid timeouts
        if aggressive:
            approx_words = int(ctx_tokens * 0.3 / tokens_per_word)  # Much smaller chunks
        else:
            approx_words = int(ctx_tokens * 0.5 / tokens_per_word)  # Reduced from 0.8 to 0.5
        max_words = max(1, approx_words)

    if n <= max_words:
        return [" ".join(words)]
    
    chunks: List[str] = []
    start = 0
    while start < n:
        end = min(start + max_words, n)
        chunks.append(" ".join(words[start:end]))
        if end == n:
            break
        start = max(0, end - overlap_words)
    return chunks


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prompt_article(
    text: str,
    target_words: int,
    language: str = "en",
) -> str:
    """Build prompt for summarizing a single article."""
    return (
        "You are a news summarization assistant.\n"
        "Write a concise summary of this news article.\n"
        f"Write a single coherent summary in {language} of about {target_words} words.\n"
        "Focus on the main facts, actors, locations, and timeline.\n"
        "Preserve key information and avoid repetition.\n"
        "Do not invent information that is not in the text.\n"
        "Write in continuous prose, no bullet points or markdown.\n\n"
        f"ARTICLE:\n{text}\n\nSUMMARY:"
    )


def _build_prompt_cluster_single(
    text: str,
    target_words: int,
    language: str = "en",
) -> str:
    return (
        "You are a news summarization assistant.\n"
        "All articles describe the same news topic.\n"
        f"Write a single coherent summary in {language} of about {target_words} words.\n"
        "Focus on the main facts, actors, locations, and timeline.\n"
        "Avoid repetition and do not invent information that is not in the text.\n"
        "Write in continuous prose, no bullet points or markdown.\n\n"
        f"TEXT:\n{text}\n\nSUMMARY:"
    )


def _build_prompt_category(
    text: str,
    num_clusters: int,
    target_words: int,
    language: str = "en",
) -> str:
    return (
        "You are writing a news category digest.\n"
        f"The input consists of summaries of {num_clusters} news clusters in the same category.\n"
        f"Write a single coherent digest in {language} of about {target_words} words.\n"
        "Cover all clusters proportionally and avoid redundancy.\n"
        "Highlight key actors, events, and how the stories relate.\n"
        "Do not invent information that is not in the text.\n"
        "Write in continuous prose, no bullet points or markdown.\n\n"
        f"TEXT:\n{text}\n\nSUMMARY:"
    )


def _build_prompt_mega(
    text: str,
    num_clusters: int,
    target_words: int,
    language: str = "en",
) -> str:
    return (
        "You are writing a global news briefing.\n"
        f"The input consists of summaries of {num_clusters} news clusters from multiple categories.\n"
        f"Write a single coherent high-level summary in {language} of about {target_words} words.\n"
        "Prioritize the most important and globally relevant stories while still covering all clusters.\n"
        "Maintain a neutral journalistic tone and avoid redundancy.\n"
        "Do not invent information that is not in the text.\n"
        "Write in continuous prose, no bullet points or markdown.\n\n"
        f"TEXT:\n{text}\n\nSUMMARY:"
    )


# ---------------------------------------------------------------------------
# Hierarchical helpers (rarely used safeguard when > context)
# ---------------------------------------------------------------------------

def _hierarchical_summarize(
    text: str,
    build_prompt,
    target_words: int,
    language: str,
) -> str:
    """Generic hierarchical safeguard, used when input ≈ beyond 128K tokens."""
    import time
    
    max_tokens = _words_to_tokens(target_words)
    ctx_tokens = llama_client.get_context_tokens()
    approx_tokens = _approx_tokens(text)
    
    # Determine if we need aggressive chunking (very large input)
    aggressive = approx_tokens > ctx_tokens * 0.9
    
    # Pre-truncate if extremely large before chunking
    if approx_tokens > ctx_tokens * 1.5:
        print(f"[SUMMARIZER] Input extremely large ({approx_tokens:,} tokens), pre-truncating before chunking...")
        max_input_words = int(ctx_tokens * 0.8 / 1.3)  # ~80% of context
        words = text.split()
        if len(words) > max_input_words:
            text = " ".join(words[:max_input_words])
            print(f"[SUMMARIZER] Pre-truncated to {len(text.split()):,} words")
    
    chunks = _chunk_text(text, aggressive=aggressive)
    print(f"[SUMMARIZER] Hierarchical summarization: splitting into {len(chunks)} chunks (aggressive={'ON' if aggressive else 'OFF'})")
    
    partials: List[str] = []
    intermediate_words = max(int(target_words / max(1, len(chunks))), 80)

    # Process chunks with retry logic
    for i, ch in enumerate(chunks, 1):
        chunk_words = len(ch.split())
        print(f"[SUMMARIZER] Processing chunk {i}/{len(chunks)} ({chunk_words:,} words)...")
        
        # Check chunk size and truncate if still too large
        chunk_tokens = _approx_tokens(ch)
        if chunk_tokens > ctx_tokens * 0.4:  # If chunk is >40% of context, truncate further
            print(f"[SUMMARIZER] Warning: Chunk {i} is {chunk_tokens:,} tokens, truncating to fit...")
            max_chunk_words = int(ctx_tokens * 0.3 / 1.3)
            chunk_words_list = ch.split()
            if len(chunk_words_list) > max_chunk_words:
                ch = " ".join(chunk_words_list[:max_chunk_words])
                print(f"[SUMMARIZER] Truncated chunk {i} to {len(ch.split()):,} words")
        
        prompt = build_prompt(ch, intermediate_words, language)
        prompt_tokens = _approx_tokens(prompt)
        prompt_chars = len(prompt)
        
        # Retry with smaller chunks if prompt is still too large
        max_retries = 2
        retry_count = 0
        success = False
        
        while retry_count <= max_retries and not success:
            try:
                if prompt_tokens > ctx_tokens * 0.5 or prompt_chars > 200000:  # 200K chars limit
                    if retry_count < max_retries:
                        print(f"[SUMMARIZER] Chunk {i} prompt still too large ({prompt_chars:,} chars), reducing chunk size...")
                        # Further reduce chunk size
                        chunk_words_list = ch.split()
                        reduced_size = int(len(chunk_words_list) * 0.6)  # Reduce by 40%
                        ch = " ".join(chunk_words_list[:reduced_size])
                        prompt = build_prompt(ch, intermediate_words, language)
                        prompt_tokens = _approx_tokens(prompt)
                        prompt_chars = len(prompt)
                        retry_count += 1
                        continue
                
                partial = llama_client.generate_raw(
                    prompt=prompt,
                    max_tokens=_words_to_tokens(intermediate_words),
                    timeout=1800,  # 30 minutes per chunk
                )
                partials.append(partial)
                print(f"[SUMMARIZER] ✓ Chunk {i}/{len(chunks)} completed ({len(partial.split()):,} words)")
                success = True
                
            except Exception as e:
                if retry_count < max_retries:
                    print(f"[SUMMARIZER] Error processing chunk {i}, retrying with smaller size... ({e})")
                    # Reduce chunk size and retry
                    chunk_words_list = ch.split()
                    reduced_size = int(len(chunk_words_list) * 0.5)  # Reduce by 50%
                    ch = " ".join(chunk_words_list[:reduced_size])
                    prompt = build_prompt(ch, intermediate_words, language)
                    retry_count += 1
                    time.sleep(2)  # Brief pause before retry
                else:
                    print(f"[SUMMARIZER] ⚠️ Failed to process chunk {i} after {max_retries} retries, skipping...")
                    # Add a placeholder to maintain structure
                    partials.append(f"[Chunk {i} processing failed - content too large]")
                    break

    if not partials:
        return "[Summary generation failed - all chunks failed to process]"
    
    # Filter out failed chunks
    valid_partials = [p for p in partials if not p.startswith("[Chunk")]
    
    if not valid_partials:
        return "[Summary generation failed - no valid chunks processed]"
    
    print(f"[SUMMARIZER] Combining {len(valid_partials)} partial summaries for final summary...")
    combined = " ".join(valid_partials)
    
    # Check if combined is too large for final summary
    combined_tokens = _approx_tokens(combined)
    if combined_tokens > ctx_tokens * 0.7:
        print(f"[SUMMARIZER] Combined summaries too large ({combined_tokens:,} tokens), truncating...")
        max_combined_words = int(ctx_tokens * 0.6 / 1.3)
        combined_words = combined.split()
        combined = " ".join(combined_words[:max_combined_words])
    
    final_prompt = build_prompt(combined, target_words, language)
    final_prompt_tokens = _approx_tokens(final_prompt)
    print(f"[SUMMARIZER] Generating final summary ({len(final_prompt.split()):,} words, {final_prompt_tokens:,} tokens in prompt)...")
    
    try:
        final = llama_client.generate_raw(
            prompt=final_prompt,
            max_tokens=max_tokens,
            timeout=900,  # 15 minutes for final summary (increased for large batches)
        )
        print(f"[SUMMARIZER] ✓ Hierarchical summarization complete")
        return final
    except Exception as e:
        print(f"[SUMMARIZER] ⚠️ Final summary generation failed: {e}")
        # Return combined partials as fallback
        return combined[:target_words * 6]  # Rough word limit


# ---------------------------------------------------------------------------
# 0) Article-level summary (single article)
# ---------------------------------------------------------------------------

def summarize_article_with_llama(
    text: str,
    target_words: int = 100,
    language: str = "en",
) -> str:
    """
    Summarize a single article.
    
    Parameters
    ----------
    text : str
        Full article text (title + body).
    target_words : int, default 100
        Target length for summary in words.
    language : str, default "en"
        Output language.
    
    Returns
    -------
    str
        Article summary.
    """
    if not text.strip():
        return ""
    
    max_tokens = _words_to_tokens(target_words)
    ctx_tokens = llama_client.get_context_tokens()
    approx_tokens = _approx_tokens(text)
    
    # Check if article is extremely long and needs hierarchical processing
    force_hierarchical = approx_tokens > ctx_tokens * 0.7
    
    # If text exceeds context window, truncate it first
    if approx_tokens > ctx_tokens:
        print(f"[SUMMARIZER] Warning: Article input text is {approx_tokens:,} tokens (>{ctx_tokens:,}), truncating to fit context window")
        max_input_words = int(ctx_tokens * 0.6 / 1.3)
        words = text.split()
        if len(words) > max_input_words:
            text = " ".join(words[:max_input_words])
            print(f"[SUMMARIZER] Truncated article input to {len(text.split()):,} words ({_approx_tokens(text):,} tokens)")
            approx_tokens = _approx_tokens(text)
            force_hierarchical = True
    
    if _needs_hierarchical(text) or force_hierarchical:
        print(f"[SUMMARIZER] Using hierarchical summarization for article (input: {_approx_tokens(text):,} tokens, context: {ctx_tokens:,})")
        summary = _hierarchical_summarize(
            text=text,
            build_prompt=_build_prompt_article,
            target_words=target_words,
            language=language,
        )
    else:
        # Build prompt and check size
        prompt = _build_prompt_article(text, target_words, language)
        prompt_tokens = _approx_tokens(prompt)
        prompt_chars = len(prompt)
        print(f"[SUMMARIZER] Built article prompt: {prompt_chars:,} chars, {prompt_tokens:,} tokens (context: {ctx_tokens:,})")
        
        # Safety check: if prompt exceeds 70% of context, use hierarchical instead
        if prompt_tokens > ctx_tokens * 0.7 or prompt_chars > 400000:
            print(f"[SUMMARIZER] Article prompt too large ({prompt_tokens:,} tokens > {int(ctx_tokens * 0.7):,} or {prompt_chars:,} chars > 400K), switching to hierarchical summarization")
            summary = _hierarchical_summarize(
                text=text,
                build_prompt=_build_prompt_article,
                target_words=target_words,
                language=language,
            )
        else:
            print(f"[SUMMARIZER] Using single-pass summarization for article")
            summary = llama_client.generate_raw(
                prompt=prompt,
                max_tokens=max_tokens,
                timeout=600,  # 10 minutes for article summarization
            )
    
    return summary


def summarize_articles_batch(
    articles: List[Dict[str, Any]],
    target_words_per_article: int = 100,
    language: str = "en",
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """
    Summarize multiple articles in parallel.
    
    Parameters
    ----------
    articles : List[Dict[str, Any]]
        List of article dicts with 'id' and 'text' keys.
        Expected format: [{"id": "art1", "text": "...", "title": "...", "body": "..."}, ...]
    target_words_per_article : int, default 100
        Target words per article summary.
    language : str, default "en"
        Output language.
    max_workers : int, default 5
        Maximum parallel workers for summarization.
    
    Returns
    -------
    List[Dict[str, Any]]
        List of article dicts with added 'summary' key.
        Format: [{"id": "art1", "text": "...", "summary": "..."}, ...]
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def summarize_single(article: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize a single article."""
        article_id = article.get("id") or article.get("url", "")
        text = article.get("text") or article.get("body", "")
        title = article.get("title", "")
        
        # Combine title and body if text not already provided
        if not text and title:
            text = f"{title}. {article.get('body', '')}"
        elif title and text and not text.startswith(title):
            text = f"{title}. {text}"
        
        if not text.strip():
            print(f"[SUMMARIZER] Skipping article {article_id} (empty text)")
            return {**article, "summary": ""}
        
        try:
            summary = summarize_article_with_llama(
                text=text,
                target_words=target_words_per_article,
                language=language,
            )
            return {**article, "summary": summary}
        except Exception as e:
            print(f"[SUMMARIZER] Error summarizing article {article_id}: {e}")
            return {**article, "summary": ""}
    
    # Summarize articles in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(summarize_single, art): art for art in articles}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                article = futures[future]
                article_id = article.get("id") or article.get("url", "unknown")
                print(f"[SUMMARIZER] Failed to summarize article {article_id}: {e}")
                results.append({**article, "summary": ""})
    
    # Preserve original order
    article_id_to_result = {r.get("id") or r.get("url"): r for r in results}
    ordered_results = [
        article_id_to_result.get(art.get("id") or art.get("url"), {**art, "summary": ""})
        for art in articles
    ]
    
    return ordered_results


# ---------------------------------------------------------------------------
# 1) Cluster-level summary (per topic)
# ---------------------------------------------------------------------------

def summarize_cluster_with_llama(
    text: str,
    num_clusters: Optional[int] = None,  # num_clusters intentionally unused here; cluster summaries are fixed-length
    language: str = "en",
) -> str:
    if not text.strip():
        return ""

    per_cluster_words, _, _ = _get_length_config()
    target_words = per_cluster_words  # e.g. 150
    max_tokens = _words_to_tokens(target_words)

    # Check if text is extremely long and needs truncation/hierarchical processing
    approx_tokens = _approx_tokens(text)
    ctx_tokens = llama_client.get_context_tokens()
    
    # Force hierarchical summarization for inputs that are close to or exceed context limit
    # Use a conservative threshold (70% of context) to account for prompt overhead
    force_hierarchical = approx_tokens > ctx_tokens * 0.7  # Use hierarchical if >70% of context
    
    # If text exceeds context window, truncate it first
    if approx_tokens > ctx_tokens:
        print(f"[SUMMARIZER] Warning: Cluster input text is {approx_tokens:,} tokens (>{ctx_tokens:,}), truncating to fit context window")
        # Truncate to ~60% of context window to leave room for prompt and response
        max_input_words = int(ctx_tokens * 0.6 / 1.3)  # ~60% of context, accounting for tokens_per_word
        words = text.split()
        if len(words) > max_input_words:
            text = " ".join(words[:max_input_words])
            print(f"[SUMMARIZER] Truncated cluster input to {len(text.split()):,} words ({_approx_tokens(text):,} tokens)")
            # Recalculate after truncation
            approx_tokens = _approx_tokens(text)
            force_hierarchical = True  # Always use hierarchical after truncation

    if _needs_hierarchical(text) or force_hierarchical:
        print(f"[SUMMARIZER] Using hierarchical summarization for cluster (input: {_approx_tokens(text):,} tokens, context: {ctx_tokens:,})")
        summary = _hierarchical_summarize(
            text=text,
            build_prompt=_build_prompt_cluster_single,
            target_words=target_words,
            language=language,
        )
    else:
        # Build prompt first to check its actual size before sending
        prompt = _build_prompt_cluster_single(text, target_words, language)
        prompt_tokens = _approx_tokens(prompt)
        prompt_chars = len(prompt)
        print(f"[SUMMARIZER] Built cluster prompt: {prompt_chars:,} chars, {prompt_tokens:,} tokens (context: {ctx_tokens:,})")
        
        # Safety check: if prompt exceeds 70% of context or is >400K chars, use hierarchical instead
        # This prevents Ollama from hanging on extremely long prompts
        if prompt_tokens > ctx_tokens * 0.7 or prompt_chars > 400000:
            print(f"[SUMMARIZER] Cluster prompt too large ({prompt_tokens:,} tokens > {int(ctx_tokens * 0.7):,} or {prompt_chars:,} chars > 400K), switching to hierarchical summarization")
            summary = _hierarchical_summarize(
                text=text,
                build_prompt=_build_prompt_cluster_single,
                target_words=target_words,
                language=language,
            )
        else:
            print(f"[SUMMARIZER] Using single-pass summarization for cluster")
            summary = llama_client.generate_raw(
                prompt=prompt,
                max_tokens=max_tokens,
                timeout=1800,  # 30 minutes for very long prompts
            )

    return summary


# ---------------------------------------------------------------------------
# 2) Category-level summary (within one news category)
# ---------------------------------------------------------------------------

def summarize_category_with_llama(
    text: str,
    num_clusters: int,
    language: str = "en",
) -> str:
    """
    text: concatenation of all cluster summaries in this category
    num_clusters: number of clusters in this category
    """
    if not text.strip():
        return ""

    per_cluster_words, max_words, _ = _get_length_config()
    target_words = min(per_cluster_words * max(num_clusters, 1), max_words)  # e.g. ≤ 1200
    max_tokens = _words_to_tokens(target_words)

    if _needs_hierarchical(text):
        summary = _hierarchical_summarize(
            text=text,
            build_prompt=lambda t, w, lang: _build_prompt_category(t, num_clusters, w, lang),
            target_words=target_words,
            language=language,
        )
    else:
        prompt = _build_prompt_category(text, num_clusters, target_words, language)
        summary = llama_client.generate_raw(
            prompt=prompt,
            max_tokens=max_tokens,
        )

    # soft truncate to target words to enforce UI word limits without re-running LLaMA
    return _soft_truncate_words(summary, target_words)


# ---------------------------------------------------------------------------
# 3) MEGA summary (across all categories)
# ---------------------------------------------------------------------------

def summarize_mega_with_llama(
    text: str,
    total_clusters: int,
    language: str = "en",
) -> str:
    """
    text: concatenation of all cluster summaries across all categories
    total_clusters: total number of clusters in the whole briefing
    """
    if not text.strip():
        return ""

    per_cluster_words, max_words, _ = _get_length_config()
    target_words = min(per_cluster_words * max(total_clusters, 1), max_words)
    max_tokens = _words_to_tokens(target_words)

    # Check if text is extremely long and needs truncation before processing
    approx_tokens = _approx_tokens(text)
    ctx_tokens = llama_client.get_context_tokens()
    
    # If text is way too long (more than 2x context), truncate it first
    if approx_tokens > ctx_tokens * 2:
        print(f"[SUMMARIZER] Warning: Input text is {approx_tokens:,} tokens (>{ctx_tokens * 2:,}), truncating to fit context window")
        # Truncate to ~80% of context window to leave room for prompt and response
        max_input_words = int(ctx_tokens * 0.8 / 1.3)  # ~80% of context, accounting for tokens_per_word
        words = text.split()
        if len(words) > max_input_words:
            text = " ".join(words[:max_input_words])
            print(f"[SUMMARIZER] Truncated to {len(text.split()):,} words ({_approx_tokens(text):,} tokens)")

    if _needs_hierarchical(text):
        print(f"[SUMMARIZER] Using hierarchical summarization (input: {_approx_tokens(text):,} tokens, context: {ctx_tokens:,})")
        summary = _hierarchical_summarize(
            text=text,
            build_prompt=lambda t, w, lang: _build_prompt_mega(t, total_clusters, w, lang),
            target_words=target_words,
            language=language,
        )
    else:
        # Build prompt first to check its actual size before sending
        prompt = _build_prompt_mega(text, total_clusters, target_words, language)
        prompt_tokens = _approx_tokens(prompt)
        prompt_chars = len(prompt)
        print(f"[SUMMARIZER] Built prompt: {prompt_chars:,} chars, {prompt_tokens:,} tokens (context: {ctx_tokens:,})")
        
        # Safety check: if prompt exceeds 80% of context or is >400K chars, use hierarchical instead
        # This prevents Ollama from hanging on extremely long prompts
        if prompt_tokens > ctx_tokens * 0.8 or prompt_chars > 400000:
            print(f"[SUMMARIZER] Prompt too large ({prompt_tokens:,} tokens > {int(ctx_tokens * 0.8):,} or {prompt_chars:,} chars > 400K), switching to hierarchical summarization")
            summary = _hierarchical_summarize(
                text=text,
                build_prompt=lambda t, w, lang: _build_prompt_mega(t, total_clusters, w, lang),
                target_words=target_words,
                language=language,
            )
        else:
            print(f"[SUMMARIZER] Using single-pass summarization")
            summary = llama_client.generate_raw(
                prompt=prompt,
                max_tokens=max_tokens,
                timeout=900,  # 15 minutes (increased for large batches)
            )

    # soft truncate to target words
    return _soft_truncate_words(summary, target_words)
