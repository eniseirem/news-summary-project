"""
lda_pipeline.py
===============

LDA (Latent Dirichlet Allocation) topic modeling pipeline for keyword extraction.

Purpose
-------
Extracts topic keywords from article clusters using LDA topic modeling. Each
cluster is analyzed to identify dominant topics and their associated keywords.
Used as supporting signals for category classification and topic labeling.

Processing
----------
- Preprocesses article text (lowercase, tokenization, stopword removal)
- Trains LDA model on cluster articles (each article = one document)
- Extracts top keywords per topic
- Calculates topic probabilities for the cluster
- Returns keywords and topic distributions

Requirements
------------
- gensim: LDA implementation
- nltk: Stopword removal
- Installation: pip install gensim nltk
- After install: python -c "import nltk; nltk.download('stopwords')"

Notes
-----
- Each article in cluster is treated as a separate document
- Adaptive passes: 3 passes for small clusters (< 5 articles), 5 for larger
- Returns top keywords per topic (default: 3 topics, 3 words each)
- Includes topic probabilities for analysis
"""

from typing import List, Dict, Any
from gensim import corpora, models
from nltk.corpus import stopwords
import re

STOPWORDS = set(stopwords.words("english"))


def preprocess_text(text: str) -> List[str]:
    """
    Basic preprocessing for LDA:
    lowercase, tokenization, stopword removal,
    removal of very short tokens.
    """
    text = text.lower()
    tokens = re.findall(r"[a-z]{3,}", text)
    tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def generate_lda_labels_for_cluster(
    cluster: Dict[str, Any],
    num_topics: int = 3,
    words_per_topic: int = 3,
) -> Dict[str, Any]:
    """
    Generate LDA topic labels for a single cluster.

    Expected input format:
    {
      "cluster_id": int,
      "articles": [
        { "id": "...", "title": "...", "body": "..." },
        ...
      ]
    }

    Output format:
    {
      "cluster_id": int,
      "lda_labels": [str, str, str]
    }
    
    
    Output format:
    {
      "cluster_id": int,
      "lda_labels": [str, ...],
      "topics": [
        {
          "topic_id": int,
          "probability": float,
          "keywords": [str, ...]
        }
      ]
    }
    """

    # Combine all article texts of the cluster
    combined_parts: List[str] = []
    for article in cluster.get("articles", []):
        combined_parts.append(article.get("title", ""))
        combined_parts.append(article.get("body", ""))

    combined_text = "\n".join(combined_parts).strip()
    if not combined_text:
        return {
            "cluster_id": cluster["cluster_id"],
            "lda_labels": [],
        }

    # Preprocess text
    tokens = preprocess_text(combined_text)
    if not tokens:
        return {
            "cluster_id": cluster["cluster_id"],
            "lda_labels": [],
        }

    articles = cluster.get("articles", [])
    if not articles:
        return {
            "cluster_id": cluster["cluster_id"],
            "lda_labels": [],    
        }

    # gensim expects a list of token lists. The pipeline expects a list of lists of tokens.
    """
    LDA sees multiple documents
    Topics emerge across articles
    Output becomes meaningful
    """
    # Preprocess each article as a separate document
    texts = [
        preprocess_text(
            article.get("title", "") + " " + article.get("body", "")
        )
        for article in articles
    ]

    texts = [t for t in texts if t]
    if not texts:
        return {
            "cluster_id": cluster["cluster_id"],
            "lda_labels": [],
            "topics": [],
        }

    # Create dictionary and corpus
    dictionary = corpora.Dictionary(texts)
    corpus = [dictionary.doc2bow(text) for text in texts]

    # Train LDA model
    # Reduced passes from 10 to 3 for faster processing while maintaining quality
    # For small clusters (< 5 articles), fewer passes are sufficient
    num_articles = len(texts)
    passes = 3 if num_articles < 5 else 5  # Faster for small clusters
    
    lda_model = models.LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=num_topics,
        passes=passes,
        random_state=42,
        iterations=50,  # Limit iterations for speed
    )

    # Extract topic labels
    lda_labels: List[str] = []
    topic_keywords_map = {}

    for topic_id in range(num_topics):
        topic_words = lda_model.show_topic(topic_id, topn=words_per_topic)
        keywords = [word for word, _ in topic_words]
        lda_labels.append(" ".join(keywords))
        topic_keywords_map[topic_id] = keywords

    # ----- Topic probabilities for the entire cluster -----
    # Build one combined "cluster document"
    combined_tokens = []
    for text in texts:
        combined_tokens.extend(text)

    bow_cluster = dictionary.doc2bow(combined_tokens)
    topic_probs = lda_model.get_document_topics(bow_cluster)

    topics_with_probs = []
    for item in topic_probs:
        topic_id, prob_value = item
        topic_id_int = int(topic_id) if isinstance(topic_id, (int, float)) else 0
        prob_float = float(prob_value) if isinstance(prob_value, (int, float)) else 0.0
        topics_with_probs.append({
            "topic_id": topic_id_int,
            "probability": round(prob_float, 3),
            "keywords": topic_keywords_map.get(topic_id_int, []),
        })

    # Sort topics by dominance
    topics_with_probs.sort(
        key=lambda x: x["probability"], reverse=True
    )

    return {
        "cluster_id": cluster["cluster_id"],
        "lda_labels": lda_labels,
        "topics": topics_with_probs,
    }

def generate_lda_labels_for_all_clusters(
    clusters: List[Dict[str, Any]],
    num_topics: int = 3,
    words_per_topic: int = 3,
) -> List[Dict[str, Any]]:
    """
    Apply LDA topic extraction to all clusters.
    """
    return [
        generate_lda_labels_for_cluster(
            cluster=cluster,
            num_topics=num_topics,
            words_per_topic=words_per_topic,
        )
        for cluster in clusters
    ]

"""   
def generate_lda_labels_for_all_clusters(
    clusters: List[Dict[str, Any]],
    num_topics: int = 3,
    words_per_topic: int = 3,
) -> List[Dict[str, Any]]:
    #Apply LDA topic labeling to all clusters.
    results = []

    for cluster in clusters:
        result = generate_lda_labels_for_cluster(
            cluster=cluster,
            num_topics=num_topics,
            words_per_topic=words_per_topic,
        )
        results.append(result)

    return results
"""

if __name__ == "__main__":
    test_cluster = {
        "cluster_id": 0,
        "articles": [
            {
                "id": "a1",
                "title": "US election campaign",
                "body": "The presidential campaign focuses on voter turnout and swing states."
            },
            {
                "id": "a2",
                "title": "Debate highlights",
                "body": "Candidates discussed foreign policy and economic reforms."
            }
        ]
    }

    result = generate_lda_labels_for_cluster(test_cluster)
    print(result)

