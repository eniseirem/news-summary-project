# Tone Validation and Soft Warnings Implementation

## Requirements

### Validation Rules:
1. **Any writing style + neutral**: ✅ Always allowed (no warnings)
2. **Any writing style + institutional**: ✅ Allowed, but softened for conversational outputs
3. **Bullet points + institutional**: ⚠️ Slightly reduce formality
4. **Conflicts (clarity vs tone)**: ❌ Fall back to neutral

## Implementation Approach

### Option 1: Pre-Validation with Warnings (Recommended)

**Validate before processing, return warnings in response, auto-adjust when needed.**

```python
def validate_tone_style_combo(
    editorial_tone: str,
    writing_style: str,
    output_format: str,
) -> Tuple[bool, List[str], Optional[str]]:
    """
    Validate tone/style/format combination and return warnings/adjustments.
    
    Returns:
        (is_valid, warnings, adjusted_tone)
    """
    warnings = []
    adjusted_tone = editorial_tone
    
    # Rule 1: neutral + anything = always OK
    if editorial_tone == "neutral":
        return True, [], editorial_tone
    
    # Rule 2: institutional + conversational styles = soften
    conversational_styles = []  
    if editorial_tone == "institutional" and writing_style in conversational_styles:
        warnings.append(
            f"Institutional tone with {writing_style} style may be too formal. "
            "Consider using neutral tone for better readability."
        )
        # Option: Auto-adjust or just warn?
        # adjusted_tone = "neutral"  # Auto-adjust
        # OR keep institutional but soften in prompt
    
    # Rule 3: bullet_points + institutional = reduce formality
    if editorial_tone == "institutional" and output_format == "bullet_points":
        warnings.append(
            "Institutional tone with bullet points format: Formality will be slightly reduced "
            "for better readability in list format."
        )
        # Soften in prompt rather than changing tone
    
    # Rule 4: Conflicts = fall back to neutral
    # Define conflicts (e.g., very casual style + very formal tone)
    conflicting_combos = [
        # Add specific conflict rules if needed
    ]
    
    return True, warnings, adjusted_tone
```

### Option 2: Prompt-Level Adjustments

**Adjust the prompt based on combinations rather than changing tone.**

```python
def get_tone_adjustment_hint(
    editorial_tone: str,
    writing_style: str,
    output_format: str,
) -> str:
    """
    Get adjustment hint for prompt based on combination.
    """
    hints = []
    
    # Rule 2: Institutional + conversational = soften
    # LinkedIn style removed - no longer checking for it
    if False:  # Removed LinkedIn check
        hints.append("While maintaining institutional authority, use a slightly more approachable tone")
    
    # Rule 3: Institutional + bullet points = reduce formality
    if editorial_tone == "institutional" and output_format == "bullet_points":
        hints.append("Use a slightly less formal tone suitable for bullet point format while maintaining professionalism")
    
    return ". ".join(hints) if hints else ""
```

### Option 3: Response Metadata

**Return warnings in response without blocking.**

```python
class StyleFormatVersion(BaseModel):
    writing_style: str
    output_format: str
    rewritten_summary: str
    warnings: List[str] = []  # Add warnings field
    tone_adjustments_applied: List[str] = []  # Track adjustments
```

## Recommended Implementation: Hybrid Approach

**Combine pre-validation + prompt adjustments + response warnings**

### Step 1: Validation Function

```python
# src/llm_engine/tone_rewriter_llama.py

def validate_and_adjust_tone_combo(
    editorial_tone: str,
    writing_style: str,
    output_format: str,
) -> Tuple[str, List[str], str]:
    """
    Validate tone/style/format combination.
    
    Returns:
        (adjusted_tone, warnings, adjustment_hint)
    """
    warnings = []
    adjustment_hint = ""
    adjusted_tone = editorial_tone
    
    # Rule 1: neutral + anything = always OK
    if editorial_tone == "neutral":
        return adjusted_tone, warnings, adjustment_hint
    
    # Rule 2: institutional + conversational = soften
    conversational_styles = []  # LinkedIn style removed
    if editorial_tone == "institutional" and writing_style in conversational_styles:
        warnings.append(
            "Institutional tone with conversational writing style: "
            "Tone will be softened for better readability while maintaining authority."
        )
        adjustment_hint = "While maintaining institutional authority, use a slightly more approachable and accessible tone"
    
    # Rule 3: institutional + bullet_points = reduce formality
    if editorial_tone == "institutional" and output_format == "bullet_points":
        warnings.append(
            "Institutional tone with bullet points: "
            "Formality will be slightly reduced for better readability in list format."
        )
        if not adjustment_hint:  # Don't override if already set
            adjustment_hint = "Use a slightly less formal tone suitable for bullet point format while maintaining professionalism"
    
    # Rule 4: Conflicts = fall back to neutral
    # Example: very casual + very formal (if we add more styles later)
    # For now, no conflicts defined
    
    return adjusted_tone, warnings, adjustment_hint
```

### Step 2: Update Prompt Template

```python
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
- The changes must be stylistic and structural only.
- Output ONLY the rewritten text with no preamble.

Editorial tone:
{editorial_tone}

{tone_adjustment_hint}

Writing style:
{writing_style}

Output format:
{output_format}

Text to rewrite:
\"\"\"{text}\"\"\"
"""
```

### Step 3: Update Rewrite Function

```python
def rewrite_summary(
    text: str,
    editorial_tone: str = "neutral",
    writing_style: str = "journalistic",
    output_format: str = "paragraph",
    language: str = "en",
    max_tokens: Optional[int] = None,
) -> Tuple[str, List[str]]:
    """
    Rewrite summary with validation and warnings.
    
    Returns:
        (rewritten_text, warnings)
    """
    if not text.strip():
        return "", []
    
    # Validate and get adjustments
    adjusted_tone, warnings, adjustment_hint = validate_and_adjust_tone_combo(
        editorial_tone, writing_style, output_format
    )
    
    tone_desc = EDITORIAL_TONES.get(adjusted_tone, EDITORIAL_TONES["neutral"])
    style_desc = WRITING_STYLES.get(writing_style, WRITING_STYLES["journalistic"])
    format_desc = OUTPUT_FORMATS.get(output_format, OUTPUT_FORMATS["paragraph"])
    
    # Build adjustment hint text
    adjustment_text = f"\n\nNote: {adjustment_hint}" if adjustment_hint else ""
    
    prompt = REWRITE_PROMPT_TEMPLATE.format(
        editorial_tone=tone_desc,
        tone_adjustment_hint=adjustment_text,
        writing_style=style_desc,
        output_format=format_desc,
        text=text.strip(),
    )
    
    rewritten = llama_client.generate_raw(
        prompt=prompt,
        max_tokens=max_tokens,
    )
    
    return rewritten.strip(), warnings
```

### Step 4: Update Response Model

```python
class StyleFormatVersion(BaseModel):
    writing_style: str
    output_format: str
    rewritten_summary: str
    editorial_tone: str  # Add tone
    warnings: List[str] = []  # Add warnings
    tone_adjustments_applied: bool = False  # Track if adjustments were made
```

### Step 5: Update Endpoint

```python
@router.post("/summarize_with_style")
def summarize_with_style_endpoint(payload: SummarizeWithStyleRequest):
    # ... existing code ...
    
    style_format_versions: List[StyleFormatVersion] = []
    for combo in combinations_to_generate:
        rewritten_summary, warnings = rewrite_summary(
            text=initial_summary,
            editorial_tone=combo.get("editorial_tone", "neutral"),
            writing_style=combo["writing_style"],
            output_format=combo["output_format"],
            language="en",
        )
        
        style_format_versions.append(
            StyleFormatVersion(
                writing_style=combo["writing_style"],
                output_format=combo["output_format"],
                rewritten_summary=rewritten_summary,
                editorial_tone=combo.get("editorial_tone", "neutral"),
                warnings=warnings,
                tone_adjustments_applied=len(warnings) > 0,
            )
        )
    
    return SummarizeWithStyleResponse(...)
```

## Alternative: Simpler Approach (Just Warnings)

If you want simpler implementation without changing return types:

```python
def get_tone_warnings(
    editorial_tone: str,
    writing_style: str,
    output_format: str,
) -> List[str]:
    """Get warnings for tone/style/format combinations."""
    warnings = []
    
    if editorial_tone == "neutral":
        return warnings  # No warnings for neutral
    
    if editorial_tone == "institutional":
        # LinkedIn style removed - no longer checking for it
        if output_format == "bullet_points":
            warnings.append(
                "Institutional tone with bullet points: Formality will be slightly reduced."
            )
    
    return warnings
```

Then add warnings to response metadata without changing function signatures.

## Recommendation

**Use Hybrid Approach:**
1. ✅ Pre-validate combinations
2. ✅ Return warnings in response
3. ✅ Adjust prompt hints (soften tone in prompt)
4. ✅ Don't block invalid combos, just warn and adjust

**Benefits:**
- Non-blocking (warnings, not errors)
- Transparent (users see what adjustments were made)
- Flexible (can adjust behavior via prompts)
- Backward compatible (doesn't break existing code)

Would you like me to implement this?
