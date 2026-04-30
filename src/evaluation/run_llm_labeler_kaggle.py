"""
LLaMA-based category evaluation on Kaggle/BBC dataset (no clustering).

Expected input (train):
- ArticleId, Text, Category

We sample N articles from train, run LLaMA to predict one of the fixed categories,
compare against ground truth, and store results as JSON in data/output.

Output per record:
{
  "article_id": "...",
  "true_category": "politics",
  "predicted_category": "politics",
  "correct": true
}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, cast

import pandas as pd

from src.llm_engine import llama_client


# Kaggle/BBC categories (normalized to lowercase)
CATEGORIES = ["business", "entertainment", "politics", "sport", "tech"]


def _normalize_category(label: str) -> str:
    if label is None:
        return ""
    return label.strip().lower().replace('"', "").replace("'", "")


def _build_prompt(text: str) -> str:
    categories_str = "\n".join(f"- {c}" for c in CATEGORIES)
    return (
        "You are classifying a news article into exactly one category.\n"
        "Choose the SINGLE best category from the list below.\n"
        "Do NOT create new categories.\n"
        "Return ONLY the category name, exactly as written.\n\n"
        "CATEGORIES:\n"
        f"{categories_str}\n\n"
        f"ARTICLE:\n{text}\n\n"
        "CATEGORY:"
    )


@dataclass
class Result:
    article_id: str
    true_category: str
    predicted_category: str
    correct: bool


def _classify_article(text: str, article_id: str) -> Tuple[str, bool]:
    """
    Classify a single article using LLaMA.
    Returns (predicted_category, success).
    """
    prompt = _build_prompt(text)

    try:
        raw = llama_client.generate_raw(
            prompt=prompt,
            max_tokens=16,
        )

        predicted = _normalize_category(raw.strip().split("\n")[0])
        
        # Validate against known categories
        for cat in CATEGORIES:
            if predicted == cat:
                return cat, True
        
        # Fallback: return first category if prediction doesn't match
        return CATEGORIES[0], False
        
    except Exception as e:
        print(f"Error classifying article {article_id}: {e}")
        return CATEGORIES[0], False


def run_evaluation(
    train_csv_path: str,
    output_json_path: str,
    sample_size: int = 100,
    random_seed: int = 42,
) -> None:
    """
    Run category classification evaluation on Kaggle/BBC dataset.
    
    Parameters
    ----------
    train_csv_path : str
        Path to CSV file with columns: ArticleId, Text, Category
    output_json_path : str
        Path to save JSON results
    sample_size : int
        Number of articles to sample and evaluate
    random_seed : int
        Random seed for sampling
    """
    random.seed(random_seed)
    
    # Load CSV
    df = pd.read_csv(train_csv_path)
    
    # Sample articles
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=random_seed)
    
    results: List[Result] = []
    
    for counter, (idx, row) in enumerate(df.iterrows(), start=1):
        article_id = str(row.get("ArticleId", str(idx)))
        text = str(row.get("Text", ""))
        true_category = _normalize_category(str(row.get("Category", "")))

        if not text.strip():
            continue
        
        predicted_category, success = _classify_article(text, article_id)
        correct = (predicted_category == true_category)
        
        results.append(Result(
            article_id=article_id,
            true_category=true_category,
            predicted_category=predicted_category,
            correct=correct,
        ))
        
        print(f"[{counter}/{len(df)}] Article {article_id}: {true_category} -> {predicted_category} ({'✓' if correct else '✗'})")
    
    # Save results
    output_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "sample_size": len(results),
        "results": [
            {
                "article_id": r.article_id,
                "true_category": r.true_category,
                "predicted_category": r.predicted_category,
                "correct": r.correct,
            }
            for r in results
        ],
        "accuracy": sum(r.correct for r in results) / len(results) if results else 0.0,
    }
    
    os.makedirs(os.path.dirname(output_json_path) or ".", exist_ok=True)
    with open(output_json_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✓ Evaluation complete!")
    print(f"  Accuracy: {output_data['accuracy']:.2%}")
    print(f"  Results saved to: {output_json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLaMA category classification on Kaggle/BBC dataset")
    parser.add_argument("--train_csv", required=True, help="Path to train CSV file")
    parser.add_argument("--output_json", required=True, help="Path to output JSON file")
    parser.add_argument("--sample_size", type=int, default=100, help="Number of articles to sample")
    parser.add_argument("--random_seed", type=int, default=42, help="Random seed for sampling")
    
    args = parser.parse_args()

    run_evaluation(
        train_csv_path=args.train_csv,
        output_json_path=args.output_json,
        sample_size=args.sample_size,
        random_seed=args.random_seed,
    )
