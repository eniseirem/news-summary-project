# Incremental Clustering Algorithm - Brief Overview

## Core Algorithm

### High-Level Flow:

```
For each new article:
  1. Generate embedding (SBERT)
  2. Find most similar existing cluster (cosine similarity)
  3. If similarity >= threshold:
     → Add article to existing cluster
     → Update cluster centroid (running average)
  4. Else:
     → Create new cluster
```

---

## Step-by-Step Algorithm

### Step 1: Generate Article Embedding
```python
# Summarize article first (prevents truncation)
summary = summarize_article(article)

# Generate embedding from summary
embedding = sbert_model.encode(summary)  # 384-dim vector
```

### Step 2: Match to Existing Clusters
```python
# For each existing cluster:
for cluster_id, cluster in existing_clusters.items():
    centroid = cluster["centroid_embedding"]  # Average embedding of all articles
    
    # Calculate cosine similarity
    similarity = cosine_similarity(article_embedding, centroid)
    # similarity = dot(article_embedding, centroid) / (norm(article) * norm(centroid))
    
    if similarity >= threshold:  # e.g., 0.7
        # Match found!
        return cluster_id
```

### Step 3: Update Existing Cluster (If Matched)
```python
# Add article to cluster
cluster["article_ids"].append(article_id)
cluster["article_count"] += 1

# Update centroid: running average
# New centroid = (old_centroid * (count-1) + new_embedding) / count
old_centroid = cluster["centroid_embedding"]
new_centroid = (old_centroid * (count - 1) + article_embedding) / count
cluster["centroid_embedding"] = new_centroid
```

### Step 4: Create New Cluster (If No Match)
```python
# No cluster found above threshold
new_cluster = {
    "cluster_id": generate_uuid(),
    "article_ids": [article_id],
    "article_count": 1,
    "centroid_embedding": article_embedding,  # First article = centroid
    "created_at": now()
}
```

---

## Key Concepts

### 1. **Centroid = Average Embedding**

**What is a centroid?**
The centroid is the "center point" of a cluster - it's the average of all article embeddings in that cluster.

**How it's calculated (element-wise average):**

Example: Cluster with 3 articles, each has a 3-dimensional embedding (simplified for clarity):

```
Article 1 embedding: [0.1, 0.2, 0.3]
Article 2 embedding: [0.2, 0.1, 0.4]
Article 3 embedding: [0.15, 0.25, 0.35]

Centroid calculation (average each position):
  Position 0: (0.1 + 0.2 + 0.15) / 3 = 0.45 / 3 = 0.15
  Position 1: (0.2 + 0.1 + 0.25) / 3 = 0.55 / 3 = 0.183
  Position 2: (0.3 + 0.4 + 0.35) / 3 = 1.05 / 3 = 0.35

Centroid = [0.15, 0.183, 0.35]
```

**In real code:**
```python
# Real embeddings are 384-dimensional (not 3)
article_1 = [0.1, 0.2, 0.3, ..., 0.05]  # 384 numbers
article_2 = [0.2, 0.1, 0.4, ..., 0.08]  # 384 numbers
article_3 = [0.15, 0.25, 0.35, ..., 0.06]  # 384 numbers

# Calculate average for each of the 384 positions
centroid = [
    (0.1 + 0.2 + 0.15) / 3,   # Position 0
    (0.2 + 0.1 + 0.25) / 3,   # Position 1
    (0.3 + 0.4 + 0.35) / 3,   # Position 2
    ...
    (0.05 + 0.08 + 0.06) / 3  # Position 383
]
# Result: [0.15, 0.183, 0.35, ..., 0.063]  # 384 numbers
```

**Why use centroid?**
- Represents the "average topic" of all articles in the cluster
- Single vector we can compare new articles against
- Instead of comparing against all articles, we compare against one centroid

---

## How Are the 384 Dimensions Created?

### The Embedding Model: SBERT (Sentence-BERT)

**Model Used**: `sentence-transformers/all-MiniLM-L6-v2`

**What it does:**
1. Takes article text as input (e.g., "Breaking news: Election results...")
2. Processes it through a neural network
3. Outputs a 384-dimensional vector (array of 384 numbers)

### Step-by-Step Process:

```
Article Text
    ↓
"Breaking news: Election results show..."
    ↓
SBERT Model (Neural Network)
    ↓
Tokenization → Word Embeddings → Transformer Layers → Pooling
    ↓
384-dimensional vector
    ↓
[0.12, -0.05, 0.33, 0.18, ..., 0.09]  # 384 numbers
```

### Why 384 Dimensions?

**The dimension is determined by the model architecture:**
- `all-MiniLM-L6-v2` was trained to output 384-dimensional vectors
- This is a design choice of the model (balance between quality and speed)
- Other models have different dimensions:
  - `all-mpnet-base-v2`: 768 dimensions (larger, better quality)
  - `all-MiniLM-L12-v2`: 384 dimensions (same size, different architecture)

**What each dimension represents:**
- Each of the 384 numbers captures some semantic meaning
- Position 0 might capture "topic similarity"
- Position 1 might capture "sentiment"
- Position 2 might capture "formality"
- etc. (not exactly, but conceptually)
- Together, all 384 numbers represent the article's meaning in a mathematical space

### How It Works in Code:

```python
from sentence_transformers import SentenceTransformer

# Load the model (384-dimensional output)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Convert article text to embedding
article_text = "Breaking news: Election results..."
embedding = model.encode(article_text)

# Result: numpy array with 384 numbers
print(embedding.shape)  # (384,)
print(embedding)  # [0.12, -0.05, 0.33, ..., 0.09]
```

### In Your Pipeline:

```python
# src/clustering/embeddings.py
def encode(texts):
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(texts)  # Returns 384-dim vectors
    return embeddings  # Shape: (num_articles, 384)
```

**Summary:**
- **384 dimensions** = Output size of the SBERT model
- **Model converts text → numbers** using neural network
- **Each dimension** captures some semantic aspect
- **Together** = Mathematical representation of article meaning

### 2. **Cosine Similarity**
```
similarity = dot(article_embedding, centroid) / (norm(article) * norm(centroid))

Range: -1 to 1
- 1.0 = Identical
- 0.7 = Very similar (threshold)
- 0.0 = Unrelated
- -1.0 = Opposite
```

### 3. **Running Average Update**

**When a new article is added to an existing cluster:**

Instead of recalculating the average from all articles (slow), we use a running average formula:

```
Before: Cluster has 4 articles
  Old centroid = C_old = [0.15, 0.2, 0.3, ...]  # Average of 4 articles

Add: Article 5 with embedding = E_new = [0.2, 0.25, 0.35, ...]

New centroid calculation:
  New centroid = (C_old * 4 + E_new) / 5

Why this works:
  - Old centroid represents average of 4 articles
  - C_old * 4 = sum of original 4 embeddings
  - Add new embedding: (sum of 4) + E_new = sum of 5
  - Divide by 5: average of all 5 articles
```

**Example with numbers:**
```
Old cluster (4 articles):
  Centroid = [0.15, 0.2, 0.3]  # Average of 4 articles

Add Article 5 with embedding = [0.2, 0.25, 0.35]

New centroid:
  Position 0: (0.15 * 4 + 0.2) / 5 = (0.6 + 0.2) / 5 = 0.8 / 5 = 0.16
  Position 1: (0.2 * 4 + 0.25) / 5 = (0.8 + 0.25) / 5 = 1.05 / 5 = 0.21
  Position 2: (0.3 * 4 + 0.35) / 5 = (1.2 + 0.35) / 5 = 1.55 / 5 = 0.31

New centroid = [0.16, 0.21, 0.31]
```

**Why use running average?**
- ✅ Fast: Don't need to load all article embeddings
- ✅ Efficient: Only need old centroid and new embedding
- ✅ Same result: Mathematically equivalent to recalculating from all articles

---

## Algorithm Pseudocode

```python
def incremental_cluster(new_articles, existing_clusters, threshold=0.7):
    results = []
    
    for article in new_articles:
        # Step 1: Generate embedding
        summary = summarize(article)
        embedding = encode(summary)
        
        # Step 2: Find best match
        best_match = None
        best_similarity = 0
        
        for cluster_id, cluster in existing_clusters.items():
            centroid = cluster["centroid_embedding"]
            similarity = cosine_similarity(embedding, centroid)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cluster_id
        
        # Step 3: Match or create
        if best_similarity >= threshold:
            # Add to existing cluster
            cluster = existing_clusters[best_match]
            cluster["article_ids"].append(article.id)
            cluster["article_count"] += 1
            
            # Update centroid (running average)
            count = cluster["article_count"]
            old_centroid = cluster["centroid_embedding"]
            new_centroid = (old_centroid * (count - 1) + embedding) / count
            cluster["centroid_embedding"] = new_centroid
            
            results.append({
                "article_id": article.id,
                "cluster_id": best_match,
                "matched": True,
                "similarity": best_similarity
            })
        else:
            # Create new cluster
            new_cluster_id = generate_uuid()
            new_cluster = {
                "cluster_id": new_cluster_id,
                "article_ids": [article.id],
                "article_count": 1,
                "centroid_embedding": embedding
            }
            existing_clusters[new_cluster_id] = new_cluster
            
            results.append({
                "article_id": article.id,
                "cluster_id": new_cluster_id,
                "matched": False,
                "similarity": best_similarity
            })
    
    return results
```

---

## Complexity

### Time Complexity:
- **Per article**: O(n) where n = number of existing clusters
  - Compare against all cluster centroids
- **Total**: O(m × n) where m = new articles, n = existing clusters

### Optimization:
- **k-NN search** (with OpenSearch): O(log n) instead of O(n)
- Only check top-k similar clusters instead of all clusters

---

## Example

### Initial State:
```
Cluster A: [art1, art2] → centroid = [0.2, 0.3, ...]
Cluster B: [art3, art4] → centroid = [0.8, 0.1, ...]
```

### New Article:
```
Article 5: embedding = [0.25, 0.28, ...]

Similarity with Cluster A: 0.85 (above 0.7 threshold) ✓
Similarity with Cluster B: 0.15 (below threshold) ✗

Result: Add to Cluster A
```

### After Update:
```
Cluster A: [art1, art2, art5] → centroid = [0.22, 0.29, ...]  # Updated average
Cluster B: [art3, art4] → centroid = [0.8, 0.1, ...]  # Unchanged
```

---

## Key Differences from Full Clustering

### Full Clustering (HDBSCAN/KMeans):
- Re-clusters ALL articles from scratch
- O(n²) or O(n log n) complexity
- No memory of previous clusters

### Incremental Clustering:
- Only processes NEW articles
- O(m × n) complexity (m = new, n = existing)
- Maintains existing clusters
- Updates centroids incrementally

---

## Summary

**Algorithm in 3 steps:**
1. **Match**: Find most similar existing cluster (cosine similarity)
2. **Update**: If match found, add article and update centroid (running average)
3. **Create**: If no match, create new cluster

**Key insight**: Use cluster centroids (average embeddings) as representatives, update them incrementally as new articles are added.
