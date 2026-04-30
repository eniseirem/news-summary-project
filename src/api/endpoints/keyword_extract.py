"""
keyword_extract.py
===================

Keywords extraction endpoint for generating LDA and TF-IDF keywords from articles.

Purpose
-------
This endpoint extracts keywords from articles using two methods:
- LDA (Latent Dirichlet Allocation): Topic modeling keywords
- TF-IDF (Term Frequency-Inverse Document Frequency): Statistical keyword extraction

Design Notes
------------
- Accepts a summary
- Returns both LDA and TF-IDF keywords
- Includes article IDs in response (optional)
- Can be used standalone or integrated into other endpoints
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re

from src.topic_labeling.lda_pipeline import preprocess_text
from src.topic_labeling.tfidf_pipeline import extract_tfidf_keywords
from gensim import corpora, models


class KeywordsRequest(BaseModel):
    """Request model for keyword extraction."""
    request_id: str
    summary: str  # Cluster or mega summary text
    extract_lda: bool = True
    extract_tfidf: bool = True
    num_topics: int = 3
    words_per_topic: int = 3
    top_k: int = 5
    article_ids: Optional[List[str]] = None


class KeywordsResponse(BaseModel):
    """Response model for keyword extraction."""
    request_id: str
    lda_keywords: Optional[List[str]] = None
    tfidf_keywords: Optional[List[str]] = None
    article_ids: Optional[List[str]] = None
    processed_at: str


router = APIRouter(tags=["keywords"])


@router.post("/keyword_extract", response_model=KeywordsResponse)
def keywords_endpoint(payload: KeywordsRequest):
    """
    Extract keywords from a cluster or mega summary using LDA and/or TF-IDF.

    Processing Steps
    ----------------
    1. Validate input summary (must not be empty)
    2. Extract LDA keywords (if enabled) - splits summary into sentences for LDA
    3. Extract TF-IDF keywords (if enabled) - works directly on summary
    4. Return keywords with article IDs

    Constraints
    -----------
    - Summary must not be empty
    - At least one extraction method must be enabled
    - LDA splits summary into sentences to simulate multiple documents
    - TF-IDF works directly on the summary text
    """
    
    # Validate input
    if not payload.summary or not payload.summary.strip():
        raise HTTPException(
            status_code=400,
            detail="Summary cannot be empty"
        )
    
    if not payload.extract_lda and not payload.extract_tfidf:
        raise HTTPException(
            status_code=400,
            detail="At least one extraction method (LDA or TF-IDF) must be enabled"
        )
    
    if payload.num_topics < 1 or payload.num_topics > 10:
        raise HTTPException(
            status_code=400,
            detail="num_topics must be between 1 and 10"
        )
    
    if payload.top_k < 1 or payload.top_k > 50:
        raise HTTPException(
            status_code=400,
            detail="top_k must be between 1 and 50"
        )
    
    lda_keywords = None
    tfidf_keywords = None
    
    # Extract LDA keywords
    if payload.extract_lda:
        try:
            # Split summary into sentences for LDA (needs multiple documents)
            # Use sentence splitting: split on periods, exclamation, question marks
            sentences = re.split(r'[.!?]+\s+', payload.summary.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # If we have sentences, process them
            if sentences:
                # Preprocess each sentence as a separate document
                texts = [preprocess_text(s) for s in sentences]
                texts = [t for t in texts if t]  # Remove empty
                
                if texts and len(texts) >= 1:
                    # Create dictionary and corpus
                    dictionary = corpora.Dictionary(texts)
                    corpus = [dictionary.doc2bow(text) for text in texts]
                    
                    # Train LDA model
                    if len(corpus) > 0:
                        lda_model = models.LdaModel(
                            corpus=corpus,
                            id2word=dictionary,
                            num_topics=min(payload.num_topics, len(corpus)),
                            random_state=42,
                            passes=10,
                            alpha='auto',
                            per_word_topics=True
                        )
                        
                        # Extract keywords from each topic
                        topic_keywords = []
                        for topic_id in range(min(payload.num_topics, lda_model.num_topics)):
                            topic_words = lda_model.show_topic(topic_id, topn=payload.words_per_topic)
                            keywords = [word for word, _ in topic_words]
                            topic_keywords.extend(keywords)
                        
                        # Remove duplicates while preserving order
                        seen = set()
                        lda_keywords = []
                        for kw in topic_keywords:
                            if kw not in seen:
                                seen.add(kw)
                                lda_keywords.append(kw)
                        lda_keywords = lda_keywords[:payload.num_topics * payload.words_per_topic]
                    else:
                        lda_keywords = []
                else:
                    lda_keywords = []
            else:
                lda_keywords = []
        except Exception as e:
            # Log error but don't fail the entire request
            print(f"[KEYWORDS] LDA extraction failed: {e}")
            lda_keywords = []
    
    # Extract TF-IDF keywords
    if payload.extract_tfidf:
        try:
            # TF-IDF can work on a single summary
            tfidf_keywords = extract_tfidf_keywords(
                texts=[payload.summary],
                top_k=payload.top_k,
            )
        except Exception as e:
            # Log error but don't fail the entire request
            print(f"[KEYWORDS] TF-IDF extraction failed: {e}")
            tfidf_keywords = []
    
    return KeywordsResponse(
        request_id=payload.request_id,
        lda_keywords=lda_keywords,
        tfidf_keywords=tfidf_keywords,
        article_ids=payload.article_ids,
        processed_at=datetime.utcnow().isoformat(),
    )
