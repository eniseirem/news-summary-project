"""
evaluate_cluster.py
===================

Lightweight endpoint for evaluating cluster summaries.

Purpose
-------
Evaluates cluster summaries using LLM judges (Qwen, Mistral, Gemma).
Returns 4 metrics: coherence, consistency, relevance, fluency (1-5 scale).

Minimal Request Format
----------------------
- cluster_summary: Summary text (string)
- source_articles: List of article texts (array of strings)
- Optional: model, cluster_id, category
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any, Tuple
from datetime import datetime

from src.evaluation.llm_judge import (
    judge_with_qwen,
    judge_with_mistral,
    judge_with_gemma,
    judge_tone_with_qwen,
    judge_tone_with_mistral,
    judge_tone_with_gemma,
    judge_style_with_qwen,
    judge_style_with_mistral,
    judge_style_with_gemma,
)


router = APIRouter(tags=["evaluation", "cluster"])

# Default fallback scores (when all judges fail)
DEFAULT_FALLBACK_MEAN = {
    "coherence": 3.0,
    "consistency": 3.0,
    "relevance": 3.0,
    "fluency": 3.0,
}

# Default fallback for optional metrics
DEFAULT_TONE_FALLBACK = 3.0
DEFAULT_STYLE_FALLBACK = 3.0


def _get_judge_fn(model: str):
    """Get judge function for model name."""
    model_lower = model.lower().strip()
    if model_lower == "qwen":
        return judge_with_qwen
    elif model_lower == "mistral":
        return judge_with_mistral
    elif model_lower == "gemma":
        return judge_with_gemma
    else:
        raise ValueError(f"Unknown model: {model}. Must be one of: qwen, mistral, gemma")


def _get_tone_judge_fn(model: str):
    """Get tone judge function for model name."""
    model_lower = model.lower().strip()
    if model_lower == "qwen":
        return judge_tone_with_qwen
    elif model_lower == "mistral":
        return judge_tone_with_mistral
    elif model_lower == "gemma":
        return judge_tone_with_gemma
    else:
        raise ValueError(f"Unknown model: {model}. Must be one of: qwen, mistral, gemma")


def _get_style_judge_fn(model: str):
    """Get style judge function for model name."""
    model_lower = model.lower().strip()
    if model_lower == "qwen":
        return judge_style_with_qwen
    elif model_lower == "mistral":
        return judge_style_with_mistral
    elif model_lower == "gemma":
        return judge_style_with_gemma
    else:
        raise ValueError(f"Unknown model: {model}. Must be one of: qwen, mistral, gemma")


def _aggregate_scores(
    results: List[Dict[str, Any]],
    drop_fallbacks: bool = True,
) -> Tuple[Dict[str, float], int, str, List[str]]:
    """
    Aggregate scores across multiple judge results.
    
    Returns:
        (aggregated_scores, num_used, overall_status, error_reasons)
    """
    metrics = ["coherence", "consistency", "relevance", "fluency"]
    used_results = []
    error_reasons = []
    
    for result in results:
        status = result.get("status", "").lower()
        if status == "failed":
            error_reasons.append(f"{result.get('model', 'unknown')}: {result.get('error', 'Unknown error')}")
            continue
        
        if drop_fallbacks and status == "fallback":
            continue
        
        if result.get("scores"):
            used_results.append(result)
    
    if not used_results:
        # All judges failed or were fallbacks → automatic fallback to default scores (3.0 for all metrics)
        return DEFAULT_FALLBACK_MEAN, 0, "fallback", error_reasons
    
    # Calculate mean scores
    aggregated = {}
    for metric in metrics:
        values = [float(r["scores"][metric]) for r in used_results if r.get("scores")]
        if values:
            aggregated[metric] = round(sum(values) / len(values), 2)
        else:
            aggregated[metric] = DEFAULT_FALLBACK_MEAN[metric]
    
    # Determine overall status
    if len(used_results) == len(results):
        overall_status = "success"
    elif len(used_results) > 0:
        overall_status = "partial"
    else:
        overall_status = "fallback"
    
    return aggregated, len(used_results), overall_status, error_reasons


def _aggregate_optional_metric(
    results: List[Dict[str, Any]],
    metric_key: str,
    default_fallback: float,
    drop_fallbacks: bool = True,
) -> Tuple[Optional[float], int, str, List[str]]:
    """
    Aggregate scores for an optional metric (tone or style) independently.
    
    Returns:
        (aggregated_score, num_used, overall_status, error_reasons)
        aggregated_score is None if metric was not evaluated
    """
    used_results = []
    error_reasons = []
    
    for result in results:
        status = result.get("status", "").lower()
        if status == "failed":
            error_reasons.append(f"{result.get('model', 'unknown')}: {result.get('error', 'Unknown error')}")
            continue
        
        if drop_fallbacks and status == "fallback":
            continue
        
        if result.get("score") is not None:
            used_results.append(result)
    
    if not used_results:
        # All judges failed or were fallbacks → automatic fallback to default score
        return default_fallback, 0, "fallback", error_reasons
    
    # Calculate mean score
    values = [float(r["score"]) for r in used_results if r.get("score") is not None]
    if values:
        aggregated_score = round(sum(values) / len(values), 2)
    else:
        aggregated_score = default_fallback
    
    # Determine overall status
    if len(used_results) == len(results):
        overall_status = "success"
    elif len(used_results) > 0:
        overall_status = "partial"
    else:
        overall_status = "fallback"
    
    return aggregated_score, len(used_results), overall_status, error_reasons


class EvaluateClusterRequest(BaseModel):
    """Minimal request for cluster summary evaluation."""
    request_id: str
    cluster_summary: str  # Summary text to evaluate
    source_articles: List[str]  # List of article texts (min 1)
    drop_fallbacks: bool = True  # Exclude fallback judges from aggregation
    evaluate_tone: bool = False  # Optional: Evaluate tone metric (5th metric)
    evaluate_style: bool = False  # Optional: Evaluate style metric (6th metric)
    cluster_id: Optional[str] = None  # Optional cluster ID
    category: Optional[str] = None  # Optional category
    article_ids: Optional[List[str]] = None  # Optional: Article IDs corresponding to source_articles


class JudgeResult(BaseModel):
    """Result from a single judge model."""
    model: str
    status: str  # "success" | "repaired" | "fallback"
    scores: Optional[Dict[str, int]] = None  # Standard 4 metrics
    tone_score: Optional[int] = None  # Optional tone score (5th metric)
    style_score: Optional[int] = None  # Optional style score (6th metric)
    error: Optional[str] = None


class EvaluateClusterResponse(BaseModel):
    """Minimal response for cluster evaluation."""
    request_id: str
    status: str  # "success" | "partial" | "fallback"
    num_judges_used: int  # Number of judges used in aggregation (0-3)
    scores: Dict[str, float]  # Averaged scores (always present: aggregated or fallback 3.0)
    tone_score: Optional[float] = None  # Optional tone score (5th metric, only if evaluate_tone=True)
    style_score: Optional[float] = None  # Optional style score (6th metric, only if evaluate_style=True)
    tone_status: Optional[str] = None  # Status for tone evaluation ("success" | "partial" | "fallback")
    style_status: Optional[str] = None  # Status for style evaluation ("success" | "partial" | "fallback")
    tone_num_judges_used: Optional[int] = None  # Number of judges used for tone aggregation
    style_num_judges_used: Optional[int] = None  # Number of judges used for style aggregation
    individual_results: List[JudgeResult]  # Per-judge results (always 3 judges)
    error_reasons: Optional[List[str]] = None  # List of error messages from failed judges
    article_ids: Optional[List[str]] = None  # Article IDs if provided
    processed_at: str


@router.post("/evaluate_cluster", response_model=EvaluateClusterResponse)
def evaluate_cluster_endpoint(payload: EvaluateClusterRequest):
    """
    Evaluate a cluster summary using all 3 LLM judges (qwen, mistral, gemma).
    
    Processing Steps
    ----------------
    1. Validate input (summary and articles must not be empty)
    2. Call all 3 judges (qwen, mistral, gemma) in parallel
    3. Aggregate scores across successful judges
    4. Return averaged scores and individual judge results
    
    Metrics (1-5 scale)
    --------------------
    Standard metrics (always evaluated):
    - coherence: Logical flow and structure
    - consistency: Factual consistency with source
    - relevance: Relevance to source articles
    - fluency: Language quality and readability
    
    Optional metrics (evaluated independently when requested):
    - tone: Editorial tone appropriateness (5th metric, set evaluate_tone=True)
    - style: Writing style appropriateness (6th metric, set evaluate_style=True)
    
    Constraints
    -----------
    - cluster_summary must not be empty
    - source_articles must have at least 1 article
    - Always uses all 3 judges: qwen, mistral, gemma
    - Optional metrics are evaluated independently and do not affect standard metrics
    
    Parameters
    ----------
    payload : EvaluateClusterRequest
        Request containing summary and articles.
    
    Returns
    -------
    EvaluateClusterResponse
        Aggregated evaluation scores and individual judge results.
    """
    
    # Validate input
    if not payload.cluster_summary or not payload.cluster_summary.strip():
        raise HTTPException(
            status_code=400,
            detail="cluster_summary cannot be empty"
        )
    
    if not payload.source_articles or len(payload.source_articles) == 0:
        raise HTTPException(
            status_code=400,
            detail="source_articles must contain at least 1 article"
        )
    
    # Filter empty articles
    valid_articles = [art.strip() for art in payload.source_articles if art and art.strip()]
    if not valid_articles:
        raise HTTPException(
            status_code=400,
            detail="All articles are empty"
        )
    
    # Format record for evaluation service
    record: Dict[str, Any] = {
        "cluster_summary": payload.cluster_summary.strip(),
        "source_articles": [{"text": art} for art in valid_articles],
    }
    
    if payload.cluster_id:
        record["cluster_id"] = payload.cluster_id
    
    if payload.category:
        record["category"] = payload.category
    
    # Always use all 3 judges: qwen, mistral, gemma
    models_to_use = ["qwen", "mistral", "gemma"]
    
    # Multi-model aggregation mode (always)
    try:
        source_text = "\n\n---\n\n".join(valid_articles)
        summary_text = payload.cluster_summary.strip()
        
        # Standard 4 metrics evaluation
        judge_results = []
        for model_name in models_to_use:
            try:
                judge_fn = _get_judge_fn(model_name)
                result = judge_fn(
                    source_text=source_text,
                    summary_text=summary_text,
                    return_meta=True,  # Get status and debug info
                )
                
                judge_results.append({
                    "model": model_name,
                    "status": result.get("status", "unknown"),
                    "scores": result.get("scores"),
                    "error": result.get("error"),
                })
            except Exception as e:
                judge_results.append({
                    "model": model_name,
                    "status": "failed",
                    "scores": None,
                    "error": str(e),
                })
        
        # Aggregate standard scores
        aggregated_scores, num_used, overall_status, error_reasons = _aggregate_scores(
            judge_results,
            drop_fallbacks=payload.drop_fallbacks,
        )
        
        # Optional tone evaluation (independent, 5th metric)
        tone_results = []
        tone_score = None
        tone_status = None
        tone_num_judges_used = None
        if payload.evaluate_tone:
            for model_name in models_to_use:
                try:
                    tone_judge_fn = _get_tone_judge_fn(model_name)
                    result = tone_judge_fn(
                        source_text=source_text,
                        summary_text=summary_text,
                        return_meta=True,
                    )
                    
                    # When return_meta=True, result is always a dict
                    result_dict = result if isinstance(result, dict) else {"score": result, "status": "success", "error": None}
                    
                    tone_results.append({
                        "model": model_name,
                        "status": result_dict.get("status", "unknown"),
                        "score": result_dict.get("score"),
                        "error": result_dict.get("error"),
                    })
                except Exception as e:
                    tone_results.append({
                        "model": model_name,
                        "status": "failed",
                        "score": None,
                        "error": str(e),
                    })
            
            tone_score, tone_num_judges_used, tone_status, tone_errors = _aggregate_optional_metric(
                tone_results,
                "tone",
                DEFAULT_TONE_FALLBACK,
                drop_fallbacks=payload.drop_fallbacks,
            )
            if tone_errors:
                error_reasons.extend([f"tone-{e}" for e in tone_errors])
        
        # Optional style evaluation (independent, 6th metric)
        style_results = []
        style_score = None
        style_status = None
        style_num_judges_used = None
        if payload.evaluate_style:
            for model_name in models_to_use:
                try:
                    style_judge_fn = _get_style_judge_fn(model_name)
                    result = style_judge_fn(
                        source_text=source_text,
                        summary_text=summary_text,
                        return_meta=True,
                    )
                    
                    # When return_meta=True, result is always a dict
                    result_dict = result if isinstance(result, dict) else {"score": result, "status": "success", "error": None}
                    
                    style_results.append({
                        "model": model_name,
                        "status": result_dict.get("status", "unknown"),
                        "score": result_dict.get("score"),
                        "error": result_dict.get("error"),
                    })
                except Exception as e:
                    style_results.append({
                        "model": model_name,
                        "status": "failed",
                        "score": None,
                        "error": str(e),
                    })
            
            style_score, style_num_judges_used, style_status, style_errors = _aggregate_optional_metric(
                style_results,
                "style",
                DEFAULT_STYLE_FALLBACK,
                drop_fallbacks=payload.drop_fallbacks,
            )
            if style_errors:
                error_reasons.extend([f"style-{e}" for e in style_errors])
        
        # Merge tone/style scores into individual results
        individual_results = []
        for r in judge_results:
            model_name = r["model"]
            tone_score_for_model = None
            style_score_for_model = None
            
            if payload.evaluate_tone:
                tone_result = next((tr for tr in tone_results if tr["model"] == model_name), None)
                if tone_result and tone_result.get("score") is not None:
                    tone_score_for_model = int(tone_result["score"])
            
            if payload.evaluate_style:
                style_result = next((sr for sr in style_results if sr["model"] == model_name), None)
                if style_result and style_result.get("score") is not None:
                    style_score_for_model = int(style_result["score"])
            
            individual_results.append(
                JudgeResult(
                    model=r["model"],
                    status=r.get("status", "unknown"),
                    scores={k: int(v) for k, v in r["scores"].items()} if r.get("scores") else None,
                    tone_score=tone_score_for_model,
                    style_score=style_score_for_model,
                    error=r.get("error"),
                )
            )
        
        return EvaluateClusterResponse(
            request_id=payload.request_id,
            status=overall_status,
            num_judges_used=num_used,
            scores=aggregated_scores,
            tone_score=tone_score,
            style_score=style_score,
            tone_status=tone_status,
            style_status=style_status,
            tone_num_judges_used=tone_num_judges_used,
            style_num_judges_used=style_num_judges_used,
            individual_results=individual_results,
            error_reasons=error_reasons if error_reasons else None,
            article_ids=payload.article_ids,
            processed_at=datetime.utcnow().isoformat(),
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )
