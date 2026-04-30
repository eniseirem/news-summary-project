"""
tone_rewriter_llama.py
======================

Post-processing module for rewriting summaries using three explicit and
independently selectable dimensions:

1. Editorial Tone
2. Writing Style
3. Output Format

Each rewrite request specifies exactly one value per dimension.
All dimensions are freely combinable.

The rewriting is purely stylistic.
No new facts may be added and the meaning must remain unchanged.

Design notes
------------
- Neutral summaries are treated as the default and can be returned as-is.
- Institutional tone is supported as an additional safe tone.
- Requests are never blocked. We auto-normalize and return soft warnings.
- A lightweight LLM-based validator can add extra soft warnings.
"""

from __future__ import annotations

import json
from typing import Optional, Tuple, List

from . import llama_client


# -----------------------------------------------------------------------
# Editorial tone definitions
# -----------------------------------------------------------------------

EDITORIAL_TONES = {
    "neutral": (
    "objective, balanced, factual framing. "
    "No evaluative language, no editorial emphasis."
),
    "institutional": (
        "institutional tone suitable for a public-sector or organizational communication: "
        "formal, impersonal, cautious wording, avoids ideological framing, avoids marketing language, "
        "no slang, no humor, no emotionally loaded phrasing"
    ),
}


# -----------------------------------------------------------------------
# Writing style definitions
# -----------------------------------------------------------------------

WRITING_STYLES = {
    "journalistic": "journalistic style, clear and factual, inverted pyramid",
    "academic": "academic style, careful wording, hedged claims",
    "executive": "executive briefing style, high-level and decision-focused",
}


# -----------------------------------------------------------------------
# Output format definitions
# -----------------------------------------------------------------------

OUTPUT_FORMATS = {
    "paragraph": (
        "a single coherent paragraph with no headings, no bullet points, "
        "and no line breaks"
    ),
    "bullet_points": (
        "a list of bullet points using '-' as the bullet symbol, "
        "one sentence per bullet, no sub-bullets, no blank lines, "
        "no paragraphs"
    ),
    "tldr": (
        "first a short TL;DR section as its own paragraph starting with "
        "'TL;DR' on a separate line, followed by a blank line, "
        "then a normal paragraph with the full rewritten summary"
    ),
    "sections": (
        "short sections with clear headers, each followed by a short paragraph"
    ),
}


# -----------------------------------------------------------------------
# Prompt templates
# -----------------------------------------------------------------------

REWRITE_PROMPT_TEMPLATE = """
Rewrite the following news summary according to the specified
editorial tone, writing style, and output format.

This is a journalism editing task, not political advocacy.

Strict rules:
- Keep all factual information accurate.
- Do NOT add new facts.
- Do NOT remove essential details.
- Do NOT change the meaning of the text.
- Preserve named entities.
- Preserve uncertainty and hedging if present.
- The changes must be stylistic and structural only.
- Output ONLY the rewritten text with no preamble.
- If there is a conflict between clarity and tone, prioritize clarity and neutral wording.

Editorial tone:
{editorial_tone}

Tone adjustment guidance:
{tone_adjustment}

Writing style:
{writing_style}

Output format:
{output_format}

Text to rewrite:
\"\"\"{text}\"\"\"
""".strip()


COMBO_VALIDATOR_PROMPT = """
You validate requested settings for rewriting a news summary.

You receive JSON with:
- editorial_tone
- writing_style
- output_format

Task:
- Identify risky or conflicting combinations that could reduce clarity or coherence.
- Do not block the request. Return soft warnings only.
- If the requested tone would reduce clarity or readability, prefer neutral wording to reduce conflicts.

Return ONLY valid JSON:
{"warnings":["short string","short string"]}
Max 5 warnings. Short and actionable.
""".strip()


# -----------------------------------------------------------------------
# Normalization and warnings
# -----------------------------------------------------------------------

def _normalize_request(
    *,
    editorial_tone: str,
    writing_style: str,
    output_format: str,
) -> Tuple[str, str, str, str, List[str]]:
    """
    Auto-normalize the requested combination. Never blocks.
    Returns:
      (tone, style, fmt, tone_adjustment, warnings)
    """
    warnings: List[str] = []

    tone = (editorial_tone or "neutral").strip().lower()
    style = (writing_style or "journalistic").strip().lower()
    fmt = (output_format or "paragraph").strip().lower()

    # Validate / fallback to known values (soft)
    if tone not in EDITORIAL_TONES:
        warnings.append(f"Unsupported editorial_tone '{tone}'. Falling back to 'neutral'.")
        tone = "neutral"

    if style not in WRITING_STYLES:
        warnings.append(f"Unsupported writing_style '{style}'. Falling back to 'journalistic'.")
        style = "journalistic"

    if fmt not in OUTPUT_FORMATS:
        warnings.append(f"Unsupported output_format '{fmt}'. Falling back to 'paragraph'.")
        fmt = "paragraph"

    # Defaults
    tone_adjustment = "None."

    # Rules derived from slides
    # Any writing style + neutral: always allowed (no adjustment)

    # Bullet points + institutional: slightly reduce formality
    if tone == "institutional" and fmt == "bullet_points":
        warnings.append(
            "Institutional tone in bullet points can sound overly rigid. "
            "Formality will be slightly reduced for clarity."
        )
        if tone_adjustment == "None.":
            tone_adjustment = "Slightly reduce formality. Keep bullets concise and clear."
        else:
            tone_adjustment += " Also slightly reduce formality for bullet points."

    return tone, style, fmt, tone_adjustment, warnings


def _llm_combo_warnings(
    *,
    editorial_tone: str,
    writing_style: str,
    output_format: str,
    language: str,
    text: str,
    max_tokens: int = 180,
) -> List[str]:
    """
    Optional LLM-based validator. If parsing fails, returns a single soft warning.
    """
    settings = {
        "editorial_tone": editorial_tone,
        "writing_style": writing_style,
        "output_format": output_format,
        "language": language,
        "text_length_chars": len(text or ""),
    }

    try:
        prompt = (
            COMBO_VALIDATOR_PROMPT
            + "\n\nSettings JSON:\n"
            + json.dumps(settings, ensure_ascii=False)
        )
        raw = llama_client.generate_raw(prompt=prompt, max_tokens=max_tokens)
        raw = raw.strip()
        if not raw.startswith("{"):
            return []
        
        obj = json.loads(raw)
        warnings = obj.get("warnings", [])
        if isinstance(warnings, list):
            cleaned = [str(w).strip() for w in warnings if str(w).strip()]
            return cleaned[:5]
        return ["Validator returned an unexpected format. Proceeding without validation."]
    except Exception:
        return ["Could not validate settings automatically. Proceeding without validation."]


# -----------------------------------------------------------------------
# Main rewrite functions
# -----------------------------------------------------------------------

def rewrite_summary(
    text: str,
    editorial_tone: str = "neutral",
    writing_style: str = "journalistic",
    output_format: str = "paragraph",
    language: str = "en",
    max_tokens: Optional[int] = None,
) -> str:
    """
    Rewrite a summary using three independent and freely combinable dimensions.

    Notes
    -----
    - Neutral is treated as a default. If editorial_tone is neutral, the input
      is returned unchanged to avoid unnecessary rewriting.
    - Use rewrite_summary_with_warnings(...) if you need auto-normalization and warnings.

    Parameters
    ----------
    text : str
        The summary text to rewrite.
    editorial_tone : str
        One of: neutral, institutional.
    writing_style : str
        One of: journalistic, academic, executive.
    output_format : str
        One of: paragraph, bullet_points, tldr, sections.
    language : str
        Output language, currently "en" only.
    max_tokens : Optional[int]
        Optional token limit override.

    Returns
    -------
    str
        The rewritten summary.
    """
    if not (text or "").strip():
        return ""

    # Neutral summaries are already the default in the pipeline
    if (editorial_tone or "neutral").strip().lower() == "neutral":
        return text.strip()

    tone = (editorial_tone or "neutral").strip().lower()
    style = (writing_style or "journalistic").strip().lower()
    fmt = (output_format or "paragraph").strip().lower()

    tone_desc = EDITORIAL_TONES.get(tone, EDITORIAL_TONES["neutral"])
    style_desc = WRITING_STYLES.get(style, WRITING_STYLES["journalistic"])
    format_desc = OUTPUT_FORMATS.get(fmt, OUTPUT_FORMATS["paragraph"])

    # Default: no extra adjustment guidance unless caller used normalize wrapper
    tone_adjustment = "None."

    prompt = REWRITE_PROMPT_TEMPLATE.format(
        editorial_tone=tone_desc,
        tone_adjustment=tone_adjustment,
        writing_style=style_desc,
        output_format=format_desc,
        text=text.strip(),
    )

    rewritten = llama_client.generate_raw(
        prompt=prompt,
        max_tokens=max_tokens,
    )

    return rewritten.strip()


def rewrite_summary_with_warnings(
    text: str,
    editorial_tone: str = "neutral",
    writing_style: str = "journalistic",
    output_format: str = "paragraph",
    language: str = "en",
    max_tokens: Optional[int] = None,
    enable_llm_validation: bool = True,
) -> dict:
    """
    Rewrite a summary with auto-normalization and soft warnings.

    Returns
    -------
    dict:
      {
        "text": <rewritten text>,
        "soft_warnings": [ ... ],
        "normalized": {
            "editorial_tone": ...,
            "writing_style": ...,
            "output_format": ...
        }
      }
    """
    if not (text or "").strip():
        return {
            "text": "",
            "soft_warnings": [],
            "normalized": {
                "editorial_tone": "neutral",
                "writing_style": "journalistic",
                "output_format": "paragraph",
            },
        }

    tone, style, fmt, tone_adjustment, warnings = _normalize_request(
        editorial_tone=editorial_tone,
        writing_style=writing_style,
        output_format=output_format,
    )

    if enable_llm_validation:
        extra = _llm_combo_warnings(
            editorial_tone=tone,
            writing_style=style,
            output_format=fmt,
            language=language,
            text=text,
        )
        for w in extra:
            if w not in warnings:
                warnings.append(w)

    # Neutral stays as-is after normalization
    if tone == "neutral":
        return {
            "text": text.strip(),
            "soft_warnings": warnings,
            "normalized": {
                "editorial_tone": tone,
                "writing_style": style,
                "output_format": fmt,
            },
        }

    tone_desc = EDITORIAL_TONES.get(tone, EDITORIAL_TONES["neutral"])
    style_desc = WRITING_STYLES.get(style, WRITING_STYLES["journalistic"])
    format_desc = OUTPUT_FORMATS.get(fmt, OUTPUT_FORMATS["paragraph"])

    prompt = REWRITE_PROMPT_TEMPLATE.format(
        editorial_tone=tone_desc,
        tone_adjustment=tone_adjustment,
        writing_style=style_desc,
        output_format=format_desc,
        text=text.strip(),
    )

    rewritten = llama_client.generate_raw(
        prompt=prompt,
        max_tokens=max_tokens,
    )

    return {
        "text": rewritten.strip(),
        "soft_warnings": warnings,
        "normalized": {
            "editorial_tone": tone,
            "writing_style": style,
            "output_format": fmt,
        },
    }
