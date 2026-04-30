"""
tfidf_pipeline.py
=================

TF-IDF keyword extraction pipeline for topic labeling.

Requirements:
- scikit-learn
- numpy
- nltk (for preprocessing consistency with LDA)
"""

from typing import List
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from topic_labeling.lda_pipeline import preprocess_text


def extract_tfidf_keywords(
    texts: List[str],
    top_k: int = 5,
    min_df: int = 1,
    max_df: float = 0.95,
) -> List[str]:
    """
    Extract top keywords from a list of texts using TF-IDF.
    
    Parameters
    ----------
    texts : List[str]
        List of text documents to extract keywords from.
    top_k : int, default 5
        Number of top keywords to return.
    min_df : int, default 1
        Minimum document frequency for a term to be included.
    max_df : float, default 0.95
        Maximum document frequency (as a proportion) for a term to be included.
    
    Returns
    -------
    List[str]
        List of top keywords ordered by TF-IDF score.
    """
    if not texts:
        return []
    
    # Filter out empty texts
    non_empty_texts = [text.strip() for text in texts if text.strip()]
    if not non_empty_texts:
        return []
    
    # Preprocess texts: use the same preprocessing as LDA for consistency
    processed_texts = []
    for text in non_empty_texts:
        # Use the same preprocessing as LDA for consistency
        tokens = preprocess_text(text)
        # Rejoin tokens for TF-IDF (it will tokenize again, but this ensures consistency)
        processed_texts.append(" ".join(tokens))
    
    if not processed_texts:
        return []
    
    # Initialize TF-IDF vectorizer
    # Increase max_features to get more candidates for filtering
    vectorizer = TfidfVectorizer(
        max_features=top_k * 5,  # Get 5x more features to ensure we have enough candidates
        min_df=min_df,
        max_df=max_df,
        stop_words="english",
        lowercase=True,
        token_pattern=r"[a-z]{3,}",  # Match words with at least 3 letters
        ngram_range=(1, 1),  # Single words only
    )
    
    try:
        # Fit and transform
        tfidf_matrix = vectorizer.fit_transform(processed_texts)
        
        # Get feature names
        feature_names = vectorizer.get_feature_names_out()
        
        if len(feature_names) == 0:
            return []
        
        # Calculate mean TF-IDF scores across all documents
        # Convert sparse matrix to dense array first
        dense_matrix = tfidf_matrix.toarray()  # type: ignore[attr-defined]
        mean_scores_array = np.mean(dense_matrix, axis=0)
        
        # Get top keywords - get more candidates than needed
        # Sort by score descending and take top candidates
        sorted_indices = mean_scores_array.argsort()[::-1]
        keywords: List[str] = []
        
        for idx in sorted_indices:
            if idx >= len(feature_names):
                continue
                
            # Relaxed filtering: include keywords with any positive score
            # This ensures we get closer to top_k keywords
            if mean_scores_array[idx] >= 0:  # Changed from > 0 to >= 0
                keyword = str(feature_names[idx]).strip()
                if keyword and keyword not in keywords:  # Avoid duplicates
                    keywords.append(keyword)
                    if len(keywords) >= top_k:
                        break
        
        return keywords[:top_k]
    except (ValueError, IndexError, AttributeError):
        # Handle case where vectorizer can't create features
        return []
