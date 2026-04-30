"""
llama_topic_labeler.py
======================

LLaMA-based topic label generation for cluster summaries.

Purpose
-------
Generates short topic labels (max 4 words) for cluster summaries using LLaMA 3
via Ollama. Topic labels are used for visualization and quick identification
of cluster themes.

Processing
----------
- Truncates summaries to 100 words for faster processing
- Uses LLaMA to generate concise topic labels
- Enforces max word limit and formatting rules
- Includes retry logic with exponential backoff
- Validates Ollama connection before processing

Notes
-----
- Requires Ollama service running locally
- Timeout: 120 seconds per attempt (topic labels are important)
- Retries: Up to 3 attempts with exponential backoff
- Format: Title case, no punctuation, no "news"/"report"/"update"
- Raises exceptions on failure (does not return fallback values)
"""

from typing import Optional
import time
import requests
from llm_engine import llama_client

def build_topic_label_prompt(
    summary: str,
    max_words: int = 4,
) -> str:
    # Truncate summary if too long to avoid timeout issues
    # Topic labels only need key information - use first 100 words for faster processing
    summary_words = summary.split()
    if len(summary_words) > 100:  # Limit to ~100 words for faster generation
        truncated = " ".join(summary_words[:100])
        print(f"[TOPIC_LABELER] Truncating summary from {len(summary_words)} to 100 words for faster topic label generation")
    else:
        truncated = summary
    
    return (
        "You are a news editor.\n"
        "Generate a short topic label for the following news summary.\n"
        f"The label must be at most {max_words} words.\n"
        "Use title case.\n"
        "Do not use punctuation.\n"
        "Do not mention 'news', 'report', or 'update'.\n\n"
        f"SUMMARY:\n{truncated}\n\n"
        "TOPIC LABEL:"
    )


def generate_cluster_topic_label(
    cluster_summary: str,
    max_words: int = 4,
    max_retries: int = 3,
) -> str:
    """
    Generate a topic label for a cluster summary using LLaMA.
    
    This function will retry up to max_retries times if generation fails.
    Raises an exception if all retries fail (does not return "Miscellaneous").
    """
    if not cluster_summary.strip():
        raise ValueError("Cannot generate topic label for empty summary")

    prompt = build_topic_label_prompt(cluster_summary, max_words)

    last_error = None
    
    for attempt in range(max_retries):
        try:
            print(f"[TOPIC_LABELER] Generating topic label (attempt {attempt + 1}/{max_retries})...")
            
            # Check Ollama health before attempting
            try:
                health_check = requests.get("http://localhost:11434/api/tags", timeout=5)
                if health_check.status_code != 200:
                    raise RuntimeError(f"Ollama health check failed: {health_check.status_code}")
            except requests.exceptions.ConnectionError:
                raise RuntimeError("Cannot connect to Ollama. Is Ollama running? Try: ollama serve")
            
            # Use longer timeout for topic labels (120 seconds) - Ollama can be slow or busy
            # Topic labels are important for visualization, so we give it more time
            raw = llama_client.generate_raw(
                prompt=prompt,
                max_tokens=16,
                timeout=120,  # Increased to 120 seconds for reliability
            )

            if not raw or not raw.strip():
                raise ValueError(f"Empty response from LLaMA: '{raw}'")

            label = raw.strip().split("\n")[0].strip()
            label = label.replace('"', "").replace("'", "").strip()
            
            if not label:
                raise ValueError(f"Empty label after processing: '{raw}'")
            
            words = label.split()
            result = " ".join(words[:max_words]) if words else None
            
            if not result:
                raise ValueError(f"Invalid label format: '{raw}'")
            
            print(f"[TOPIC_LABELER] ✓ Successfully generated topic label: '{result}'")
            return result
                
        except requests.exceptions.Timeout as e:
            last_error = e
            error_msg = f"Request timed out after 120 seconds (attempt {attempt + 1}/{max_retries})"
            print(f"[TOPIC_LABELER] ⚠️ {error_msg}")
            print(f"[TOPIC_LABELER] Ollama may be stuck or overloaded. Consider restarting: pkill -9 ollama && ollama serve")
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)  # Longer backoff: 5s, 10s, 15s
                print(f"[TOPIC_LABELER] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Topic label generation timed out after {max_retries} attempts: {error_msg}") from e
                
        except requests.exceptions.ConnectionError as e:
            last_error = e
            error_msg = f"Cannot connect to Ollama (attempt {attempt + 1}/{max_retries})"
            print(f"[TOPIC_LABELER] ⚠️ {error_msg}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[TOPIC_LABELER] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Topic label generation failed: Cannot connect to Ollama. Is Ollama running?") from e
                
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            error_msg = str(e) if e else "Unknown error"
            print(f"[TOPIC_LABELER] ⚠️ Error ({error_type}): {error_msg} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"[TOPIC_LABELER] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Topic label generation failed after {max_retries} attempts: {error_type}: {error_msg}") from e
    
    # Should never reach here, but just in case
    raise RuntimeError(f"Topic label generation failed after {max_retries} attempts. Last error: {last_error}")
