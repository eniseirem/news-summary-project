"""
tone_rewriter_llama_plain.py
============================

Plain post-processing module for rewriting summaries with three independently
selectable dimensions:

1. Editorial tone (optional)
2. Writing style (optional)
3. Output format (optional)

All dimensions are freely combinable and fully optional.
If nothing is selected, the input text is returned unchanged.

The rewriting is purely stylistic.
No new facts may be added and the meaning must remain unchanged.
"""

from __future__ import annotations

from typing import Optional

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
# Prompt template
# -----------------------------------------------------------------------

REWRITE_PROMPT_TEMPLATE = """
Rewrite the following news summary according to the specified dimensions.

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
- ONLY use information that is explicitly present in the input text.
- Do NOT infer causes, implications, or missing details.
- For bullet points: convert each input sentence into at most one bullet. Do not create additional bullets.
- Keep the number of sentences the same as the input unless the requested output format requires a fixed structure (e.g. TL;DR line + full paragraph).


Editorial tone:
{editorial_tone}

Writing style:
{writing_style}

Output format:
{output_format}

Text to rewrite:
\"\"\"{text}\"\"\"
""".strip()


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip().lower()
    return v if v else None


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def rewrite_summary_plain(
    text: str,
    *,
    editorial_tone: Optional[str] = None,
    writing_style: Optional[str] = None,
    output_format: Optional[str] = None,
    language: str = "en",
    max_tokens: Optional[int] = None,
) -> str:
    """
    Plain rewrite function with fully optional dimensions.

    If all dimensions are None or empty, the input text is returned unchanged.
    Unknown values are ignored instead of normalized or warned about.
    """
    if not (text or "").strip():
        return ""

    tone = _normalize_optional(editorial_tone)
    style = _normalize_optional(writing_style)
    fmt = _normalize_optional(output_format)

    if tone not in EDITORIAL_TONES:
        tone = None
    if style not in WRITING_STYLES:
        style = None
    if fmt not in OUTPUT_FORMATS:
        fmt = None

    if tone is None and style is None and fmt is None:
        return text.strip()

    tone_desc = EDITORIAL_TONES.get(tone or "neutral", EDITORIAL_TONES["neutral"])
    style_desc = WRITING_STYLES.get(style or "journalistic", WRITING_STYLES["journalistic"])
    format_desc = OUTPUT_FORMATS.get(fmt or "paragraph", OUTPUT_FORMATS["paragraph"])

    prompt = REWRITE_PROMPT_TEMPLATE.format(
        editorial_tone=tone_desc,
        writing_style=style_desc,
        output_format=format_desc,
        text=text.strip(),
    )

    rewritten = llama_client.generate_raw(
        prompt=prompt,
        max_tokens=max_tokens,
    )

    return rewritten.strip()
