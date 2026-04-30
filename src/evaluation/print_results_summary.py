"""
Print formatted summary from existing evaluation results.

Reads all test_kaggle_results_*.json files from a directory and prints
a formatted summary table suitable for screenshots.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Kaggle/BBC categories
CATEGORIES = ["business", "entertainment", "politics", "sport", "tech"]


def load_results_from_directory(results_dir: str) -> List[Dict]:
    """Load all result JSON files from the directory."""
    results_dir_path = Path(results_dir)
    
    if not results_dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {results_dir}")
    
    all_results = []
    
    # Find all test_kaggle_results_*.json files
    result_files = sorted(results_dir_path.glob("test_kaggle_results_*.json"))
    
    if not result_files:
        raise FileNotFoundError(f"No result files found in {results_dir}")
    
    print(f"📂 Found {len(result_files)} result files in {results_dir}")
    
    for result_file in result_files:
        with open(result_file, "r", encoding="utf-8") as f:
            batch_results = json.load(f)
            all_results.extend(batch_results)
    
    return all_results


def calculate_statistics(results: List[Dict]) -> Dict:
    """Calculate overall and per-category statistics."""
    total_seen = len(results)
    total_correct = sum(1 for r in results if r.get("correct", False))
    
    # Per-category statistics
    category_stats = {
        cat: {"total": 0, "correct": 0, "incorrect": 0}
        for cat in CATEGORIES
    }
    
    for result in results:
        true_cat = result.get("true_category", "").lower()
        correct = result.get("correct", False)
        
        if true_cat in category_stats:
            category_stats[true_cat]["total"] += 1
            if correct:
                category_stats[true_cat]["correct"] += 1
            else:
                category_stats[true_cat]["incorrect"] += 1
    
    return {
        "total_seen": total_seen,
        "total_correct": total_correct,
        "total_incorrect": total_seen - total_correct,
        "overall_accuracy": (total_correct / total_seen * 100) if total_seen > 0 else 0.0,
        "category_stats": category_stats,
    }


def print_formatted_summary(stats: Dict, n_batches: Optional[int] = None):
    """Print the formatted summary table."""
    print("\n" + "=" * 80)
    print(" " * 25 + "EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print()
    
    print(" OVERALL PERFORMANCE")
    print("-" * 80)
    print(f"  Total Articles Evaluated:    {stats['total_seen']:>6}")
    print(f"  Correct Predictions:         {stats['total_correct']:>6}")
    print(f"  Incorrect Predictions:       {stats['total_incorrect']:>6}")
    print(f"  Overall Accuracy:            {stats['overall_accuracy']:>6.2f}%")
    print()
    
    print(" PER-CATEGORY ACCURACY BREAKDOWN")
    print("-" * 80)
    print(f"  {'Category':<20} {'Total':>8} {'Correct':>8} {'Accuracy':>12}")
    print("  " + "-" * 48)
    
    for cat in CATEGORIES:
        cat_stats = stats['category_stats'][cat]
        cat_total = cat_stats["total"]
        cat_correct = cat_stats["correct"]
        cat_accuracy = (cat_correct / cat_total * 100) if cat_total > 0 else 0.0
        cat_name = cat.capitalize()
        print(f"  {cat_name:<20} {cat_total:>8} {cat_correct:>8} {cat_accuracy:>11.2f}%")
    
    print()
    print(" EVALUATION CONFIGURATION")
    print("-" * 80)
    print(f"  Dataset:                     Kaggle/BBC News")
    print(f"  Model:                       LLaMA 3.2 (via Ollama)")
    if n_batches:
        print(f"  Number of Batches:           {n_batches}")
    print(f"  Categories Evaluated:        {', '.join([c.capitalize() for c in CATEGORIES])}")
    print()
    
    print("=" * 80)
    print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Print formatted summary from existing evaluation results"
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default="data/output/run_full",
        help="Directory containing test_kaggle_results_*.json files"
    )
    
    args = parser.parse_args()
    
    # Load results
    results = load_results_from_directory(args.results_dir)
    
    # Count batches (number of result files)
    result_files = list(Path(args.results_dir).glob("test_kaggle_results_*.json"))
    n_batches = len(result_files)
    
    # Calculate statistics
    stats = calculate_statistics(results)
    
    # Print formatted summary
    print_formatted_summary(stats, n_batches=n_batches)


if __name__ == "__main__":
    main()
