#!/usr/bin/env python3
"""
Test script to demonstrate styling pipeline with three writing styles.
"""

import sys
import os
import traceback

# Add src to path (go up one level from tests/ to project root)
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))

try:
    from api.schemas import Article  # type: ignore
    from llm_engine.model_loader import get_summarizer_backend  # type: ignore
    from llm_engine.tone_rewriter_llama_plain import rewrite_summary_plain  # type: ignore
except Exception as e:
    print(f"Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test article
article_text = """TechCorp announced Q3 revenue of $2.5 billion, up 15% year-over-year. The company credits growth to cloud services and AI products. CEO Jane Smith said the results reflect strong demand and operational efficiency. The company raised its full-year forecast and plans to expand into European markets next quarter."""

# Create article object
article = Article(
    id="test_001",
    title="Tech Company Reports Strong Q3 Earnings",
    body=article_text,
    language="en"
)

print("=" * 80)
print("ORIGINAL ARTICLE")
print("=" * 80)
print(f"Title: {article.title}")
print(f"Body: {article.body}\n")

# Step 1: Generate base summary
print("Generating base summary...")
try:
    backend = get_summarizer_backend()
    combined_text = f"{article.title}. {article.body}"
    initial_summary = backend.summarize(
        text=combined_text,
        summary_length="medium",
        language="en",
    )
except Exception as e:
    print(f"Error generating summary: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("BASE SUMMARY")
print("=" * 80)
print(initial_summary + "\n")

# Step 2: Generate three style variations with neutral tone
styles = ["journalistic", "academic", "executive"]

print("=" * 80)
print("STYLED VERSIONS (Neutral Tone)")
print("=" * 80)

for style in styles:
    print(f"\n--- {style.upper()} STYLE ---")
    try:
        rewritten = rewrite_summary_plain(
            text=initial_summary,
            editorial_tone=None,  # neutral
            writing_style=style,
            output_format="paragraph",
            language="en",
        )
        print(rewritten)
    except Exception as e:
        print(f"Error rewriting with {style} style: {e}")
        traceback.print_exc()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
