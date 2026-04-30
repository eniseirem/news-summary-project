from fastapi import FastAPI, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List, Literal, Dict, Any, Union
from pydantic import BaseModel, Field, constr, conint, confloat
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
import uuid
import re

app = FastAPI()

client = OpenSearch(
    hosts=[{"host": "opensearch", "port": 9200}],
    http_auth=("admin", "admin"),
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
)

def now_iso() -> str:
    return datetime.utcnow().isoformat()

def require_fields(payload: dict, fields: list):
    missing = [f for f in fields if f not in payload or payload[f] in [None, ""]]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

def index_required(index: str, e: Exception):
    raise HTTPException(
        status_code=500,
        detail=f"OpenSearch index missing or not reachable: '{index}'. Create the index first. ({type(e).__name__})"
    )

def exists(index: str, field: str, value: str) -> bool:
    # legacy helper (uses match)
    try:
        res = client.search(index=index, body={"query": {"match": {field: value}}})
        return res["hits"]["total"]["value"] > 0
    except NotFoundError as e:
        index_required(index, e)

def exists_term(index: str, field: str, value: str) -> bool:
    try:
        res = client.search(index=index, body={"size": 0, "query": {"term": {field: value}}})
        return res["hits"]["total"]["value"] > 0
    except NotFoundError as e:
        index_required(index, e)

def ingest(index: str, payload: dict, doc_id: str = None):
    payload["ingested_at"] = now_iso()
    try:
        return client.index(index=index, id=doc_id, body=payload)
    except NotFoundError as e:
        index_required(index, e)

def store_doc(index: str, doc: dict, doc_id: Optional[str] = None) -> dict:
    doc["ingested_at"] = now_iso()
    try:
        client.index(index=index, id=doc_id, body=doc)
        return doc
    except NotFoundError as e:
        index_required(index, e)

@app.get("/")
def root():
    return {"status": "API online"}
# ---------------------------
# 1) /summarize_with_style_plain
# ---------------------------
class SummarizeWithStylePlainRequest(BaseModel):
    request_id: str
    summary: constr(min_length=1)
    writing_style: Optional[Literal["journalistic", "academic", "executive", "linkedin"]] = None
    output_format: Optional[Literal["paragraph", "bullet_points", "tldr", "sections"]] = None
    institutional: bool = False
    article_ids: Optional[List[str]] = None

@app.post("/summarize_with_style_plain")
def summarize_with_style_plain(payload: SummarizeWithStylePlainRequest):
    if exists_term("summarize_with_style_plain", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "styled_summary": payload.summary,
        "institutional": payload.institutional,
        "processed_at": processed_at,
    }
    if payload.writing_style is not None:
        resp["writing_style"] = payload.writing_style
    if payload.output_format is not None:
        resp["output_format"] = payload.output_format
    if payload.article_ids is not None:
        resp["article_ids"] = payload.article_ids

    store_doc("summarize_with_style_plain", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 2) /topic_label
# ---------------------------
class TopicLabelRequest(BaseModel):
    request_id: str
    summary: constr(min_length=1)
    article_ids: Optional[List[str]] = None
    max_words: conint(ge=1, le=10) = 4

def _simple_topic_label(text: str, max_words: int) -> str:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", text)
    tokens = [t for t in tokens if len(t) > 2][:max_words]
    if not tokens:
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", text)[:max_words]
    label = " ".join(tokens).strip()
    return label[:120] if label else "Topic"

@app.post("/topic_label")
def topic_label(payload: TopicLabelRequest):
    if exists_term("topic_label", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()
    label = _simple_topic_label(payload.summary, payload.max_words)

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "topic_label": label,
        "processed_at": processed_at,
    }
    # optional response fields
    if payload.article_ids is not None:
        resp["article_ids"] = payload.article_ids
    resp["summary_length"] = len(payload.summary)
    resp["max_words"] = payload.max_words

    store_doc("topic_label", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 3) /keywords
# ---------------------------
class KeywordsRequest(BaseModel):
    request_id: str
    summary: constr(min_length=1)
    extract_lda: bool = True
    extract_tfidf: bool = True
    num_topics: conint(ge=1, le=10) = 3
    words_per_topic: conint(ge=1, le=50) = 3
    top_k: conint(ge=1, le=50) = 5
    article_ids: Optional[List[str]] = None

def _simple_keywords(text: str, k: int) -> List[str]:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß]+", text.lower())
    stop = set(["the", "and", "or", "for", "with", "this", "that", "from", "into", "over", "under", "aber", "und", "oder", "für", "mit", "dass", "der", "die", "das"])
    tokens = [t for t in tokens if t not in stop and len(t) > 3]
    seen = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
        if len(seen) >= k:
            break
    return seen[:k]

@app.post("/keywords")
def keywords(payload: KeywordsRequest):
    if not (payload.extract_lda or payload.extract_tfidf):
        raise HTTPException(status_code=400, detail="At least one of extract_lda/extract_tfidf must be true")

    if exists_term("keywords", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()
    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "processed_at": processed_at,
    }

    base = _simple_keywords(payload.summary, max(payload.top_k, payload.num_topics * payload.words_per_topic))
    if payload.extract_lda:
        resp["lda_keywords"] = base[: max(1, payload.num_topics * payload.words_per_topic)]
    if payload.extract_tfidf:
        resp["tfidf_keywords"] = base[: payload.top_k]

    if payload.article_ids is not None:
        resp["article_ids"] = payload.article_ids

    store_doc("keywords", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 4) /category_label
# ---------------------------
class CategoryLabelRequest(BaseModel):
    request_id: str
    summary: constr(min_length=1)
    article_count: conint(ge=1)
    article_ids: Optional[List[str]] = None
    lda_keywords: Optional[List[str]] = None
    use_lda: bool = True
    is_noise_cluster: bool = False
    cluster_id: Optional[int] = None

Category = Literal["Global Politics", "Economics", "Sports", "Events", "General News"]

def _guess_category(text: str) -> Category:
    t = text.lower()
    if any(w in t for w in ["football", "soccer", "basketball", "tennis", "match", "tournament", "bundesliga", "premier"]):
        return "Sports"
    if any(w in t for w in ["inflation", "stocks", "market", "gdp", "economy", "tariff", "bank", "interest"]):
        return "Economics"
    if any(w in t for w in ["election", "parliament", "government", "minister", "president", "war", "nato", "un", "sanction"]):
        return "Global Politics"
    if any(w in t for w in ["festival", "earthquake", "storm", "summit", "conference", "protest", "attack"]):
        return "Events"
    return "General News"

@app.post("/category_label")
def category_label(payload: CategoryLabelRequest):
    if exists_term("category_label", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()

    basis = payload.summary
    if payload.use_lda and payload.lda_keywords:
        basis = basis + " " + " ".join(payload.lda_keywords)

    category: Category = "General News" if payload.is_noise_cluster else _guess_category(basis)

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "category": category,
        "article_count": payload.article_count,
        "processed_at": processed_at,
    }
    if payload.article_ids is not None:
        resp["article_ids"] = payload.article_ids
    if payload.cluster_id is not None:
        resp["cluster_id"] = payload.cluster_id
    resp["summary_length"] = len(payload.summary)
    resp["used_lda"] = bool(payload.use_lda and payload.lda_keywords)
    resp["is_noise_cluster"] = payload.is_noise_cluster

    store_doc("category_label", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# Shared: Article schema
# ---------------------------
class Article(BaseModel):
    id: str
    title: str
    body: str
    language: str
    source: Optional[str] = None
    published_at: Optional[str] = None

# ---------------------------
# 5) /cluster_incremental_n8n
# ---------------------------
class ClusterCentroid(BaseModel):
    cluster_id: str
    centroid_embedding: List[float] = Field(..., description="384-dim vector")
    current_article_count: Optional[int] = None

class ClusterIncrementalRequest(BaseModel):
    request_id: str
    articles: List[Article] = Field(..., min_length=1)
    cluster_centroids: List[ClusterCentroid]
    similarity_threshold: Optional[confloat(ge=0.0, le=1.0)] = 0.7
    min_cluster_size: Optional[conint(ge=1)] = 2

@app.post("/cluster_incremental_n8n")
def cluster_incremental_n8n(payload: ClusterIncrementalRequest):
    """
    Placeholder implementation:
    - No real embedding matching implemented here.
    - Treats all incoming articles as new clusters.
    - Persists clusters into OpenSearch index 'clusters' (id = cluster_id).
    """
    processed_at = now_iso()

    new_clusters = []
    article_matches = []

    for a in payload.articles:
        cid = f"cluster_{uuid.uuid4().hex}"
        created_at = processed_at
        centroid = [0.0] * 384  # placeholder vector
        cluster_doc = {
            "cluster_id": cid,
            "article_ids": [a.id],
            "article_count": 1,
            "centroid_embedding": centroid,
            "created_at": created_at,
        }
        # store cluster state
        store_doc("clusters", dict(cluster_doc), doc_id=cid)

        new_clusters.append(cluster_doc)
        article_matches.append({"article_id": a.id, "is_new_cluster": True, "new_cluster_id": cid})

    resp = {
        "request_id": payload.request_id,
        "total_articles": len(payload.articles),
        "matched_articles": 0,
        "new_clusters_created": len(new_clusters),
        "new_articles_in_new_clusters": len(payload.articles),
        "article_matches": article_matches,
        "matched_cluster_updates": [],
        "new_clusters": new_clusters,
        "total_existing_clusters": len(payload.cluster_centroids),
        "processed_at": processed_at,
    }
    return resp

# ---------------------------
# 6) /cluster_maintenance
# ---------------------------
class ClusterMaintenanceRequest(BaseModel):
    request_id: str
    operation: Literal["merge", "archive", "cleanup", "all"]
    similarity_threshold: Optional[confloat(ge=0.0, le=1.0)] = 0.85
    days_inactive: Optional[conint(ge=1)] = 30

@app.post("/cluster_maintenance")
def cluster_maintenance(payload: ClusterMaintenanceRequest):
    processed_at = now_iso()

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "operation": payload.operation,
        "processed_at": processed_at,
    }

    if payload.operation in ["merge", "all"]:
        resp["merges"] = []
    if payload.operation in ["archive", "all"]:
        resp["archived"] = {"archived_cluster_ids": [], "total_archived": 0}
    if payload.operation in ["cleanup", "all"]:
        resp["duplicates_merged"] = []

    store_doc("cluster_maintenance", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 7) /cluster_stats
# ---------------------------
@app.get("/cluster_stats")
def cluster_stats(request_id: str = Query(default="stats_request")):
    processed_at = now_iso()

    try:
        client.indices.get(index="clusters")
        index_available = True
    except NotFoundError:
        index_available = False

    if not index_available:
        return {
            "request_id": request_id,
            "total_clusters": 0,
            "active_clusters": 0,
            "archived_clusters": 0,
            "total_articles": 0,
            "avg_cluster_size": 0.0,
            "processed_at": processed_at,
            "size_distribution": [],
            "category_distribution": [],
            "recent_activity": {"clusters_created_last_7_days": 0, "clusters_updated_last_7_days": 0},
            "storage_info": {"storage_type": "opensearch", "total_clusters": 0, "index_available": False},
        }

    # totals
    total_clusters = client.count(index="clusters", body={"query": {"match_all": {}}}).get("count", 0)

    # archived
    try:
        archived_clusters = client.count(
            index="clusters",
            body={"query": {"term": {"is_archived": True}}},
        ).get("count", 0)
    except Exception:
        archived_clusters = 0

    active_clusters = max(0, total_clusters - archived_clusters)

    # total articles
    total_articles = 0
    try:
        agg = client.search(
            index="clusters",
            body={"size": 0, "aggs": {"total_articles": {"sum": {"field": "article_count"}}}},
        )
        total_articles = int(agg.get("aggregations", {}).get("total_articles", {}).get("value", 0) or 0)
    except Exception:
        total_articles = 0

    avg_cluster_size = float(total_articles) / float(active_clusters) if active_clusters > 0 else 0.0

    return {
        "request_id": request_id,
        "total_clusters": total_clusters,
        "active_clusters": active_clusters,
        "archived_clusters": archived_clusters,
        "total_articles": total_articles,
        "avg_cluster_size": round(avg_cluster_size, 2),
        "processed_at": processed_at,
        "size_distribution": [],
        "category_distribution": [],
        "recent_activity": {"clusters_created_last_7_days": 0, "clusters_updated_last_7_days": 0},
        "storage_info": {"storage_type": "opensearch", "total_clusters": total_clusters, "index_available": True},
    }

# ---------------------------
# 8) /evaluate/cluster
# ---------------------------
class EvaluateClusterRequest(BaseModel):
    request_id: str
    cluster_summary: constr(min_length=1)
    source_articles: List[constr(min_length=1)] = Field(..., min_length=1)
    drop_fallbacks: bool = True
    cluster_id: Optional[str] = None
    category: Optional[str] = None
    article_ids: Optional[List[str]] = None

@app.post("/evaluate/cluster")
def evaluate_cluster(payload: EvaluateClusterRequest):
    if exists_term("evaluate_cluster", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()

    # Placeholder judge results
    individual_results = [
        {"model": "qwen", "status": "fallback", "scores": None, "error": "Not implemented"},
        {"model": "mistral", "status": "fallback", "scores": None, "error": "Not implemented"},
        {"model": "gemma", "status": "fallback", "scores": None, "error": "Not implemented"},
    ]
    scores = {"coherence": 3.0, "consistency": 3.0, "relevance": 3.0, "fluency": 3.0}

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "status": "fallback",
        "num_judges_used": 0,
        "scores": scores,
        "individual_results": individual_results,
        "error_reasons": ["qwen: Not implemented", "mistral: Not implemented", "gemma: Not implemented"],
        "processed_at": processed_at,
    }
    if payload.article_ids is not None:
        resp["article_ids"] = payload.article_ids
    if payload.cluster_id is not None:
        resp["cluster_id"] = payload.cluster_id
    if payload.category is not None:
        resp["category"] = payload.category

    store_doc("evaluate_cluster", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 9) /evaluate/mega
# ---------------------------
class EvaluateMegaRequest(BaseModel):
    request_id: str
    mega_summary: constr(min_length=1)
    cluster_summaries: Dict[str, constr(min_length=1)]
    drop_fallbacks: bool = True
    cluster_article_ids: Optional[Dict[str, List[str]]] = None

@app.post("/evaluate/mega")
def evaluate_mega(payload: EvaluateMegaRequest):
    if exists_term("evaluate_mega", "request_id", payload.request_id):
        raise HTTPException(status_code=409, detail="request_id already exists")

    processed_at = now_iso()

    individual_results = [
        {"model": "qwen", "status": "fallback", "scores": None, "error": "Not implemented"},
        {"model": "mistral", "status": "fallback", "scores": None, "error": "Not implemented"},
        {"model": "gemma", "status": "fallback", "scores": None, "error": "Not implemented"},
    ]
    scores = {"coherence": 3.0, "consistency": 3.0, "relevance": 3.0, "fluency": 3.0}

    resp: Dict[str, Any] = {
        "request_id": payload.request_id,
        "status": "fallback",
        "num_judges_used": 0,
        "scores": scores,
        "individual_results": individual_results,
        "error_reasons": ["qwen: Not implemented", "mistral: Not implemented", "gemma: Not implemented"],
        "processed_at": processed_at,
    }
    if payload.cluster_article_ids is not None:
        resp["cluster_article_ids"] = payload.cluster_article_ids

    store_doc("evaluate_mega", dict(resp), doc_id=payload.request_id)
    return resp

# ---------------------------
# 10) /translate/cluster_summary_de
# ---------------------------
class TranslateClusterSummaryDeRequest(BaseModel):
    payload: Dict[str, Any]

@app.post("/translate/cluster_summary_de")
def translate_cluster_summary_de(req: TranslateClusterSummaryDeRequest):
    p = dict(req.payload)
    cs = dict(p.get("cluster_summary", {}))
    summary = cs.get("summary", "")
    cs["summary_de"] = summary
    p["cluster_summary"] = cs
    return {"payload": p}

# ---------------------------
# 11) /translate/mega_summary_de
# ---------------------------
class TranslateMegaSummaryDeRequest(BaseModel):
    payload: Dict[str, Any]

@app.post("/translate/mega_summary_de")
def translate_mega_summary_de(req: TranslateMegaSummaryDeRequest):
    p = dict(req.payload)
    ms = dict(p.get("mega_summary", {}))
    ms_sum = ms.get("summary", "")
    ms["summary_de"] = ms_sum  # placeholder
    p["mega_summary"] = ms

    cs_map = p.get("cluster_summaries")
    if isinstance(cs_map, dict):
        new_cs = {}
        for k, v in cs_map.items():
            if isinstance(v, dict):
                vv = dict(v)
                vv["summary_de"] = vv.get("summary", "")
                new_cs[k] = vv
            else:
                new_cs[k] = v
        p["cluster_summaries"] = new_cs

    return {"payload": p}

# ---------------------------
# 12) /cluster_summary_from_clusters
# ---------------------------
class ClusterSummaryInput(BaseModel):
    cluster_id: str
    article_ids: List[str]

class ClusterSummarizeRequest(BaseModel):
    request_id: str
    clusters: List[ClusterSummaryInput]
    articles: List[Article]
    article_summaries: Optional[Dict[str, str]] = None

@app.post("/cluster_summary_from_clusters")
def cluster_summary_from_clusters(payload: ClusterSummarizeRequest):
    processed_at = now_iso()
    results = []

    for c in payload.clusters:
        summaries = []

        if payload.article_summaries:
            for aid in c.article_ids:
                if aid in payload.article_summaries:
                    summaries.append(payload.article_summaries[aid])

        if not summaries:
            # Fallback: naive concat (placeholder)
            summaries = [a.body for a in payload.articles if a.id in c.article_ids]

        cluster_summary = " ".join(summaries)[:4000]

        doc = {
            "request_id": payload.request_id,
            "cluster_id": c.cluster_id,
            "article_ids": c.article_ids,
            "article_count": len(c.article_ids),
            "summary": cluster_summary,
            "processed_at": processed_at,
        }

        store_doc("cluster_summaries", dict(doc), doc_id=f"{payload.request_id}_{c.cluster_id}")
        results.append(doc)

    return {
        "request_id": payload.request_id,
        "cluster_count": len(results),
        "clusters": results,
        "processed_at": processed_at,
    }

# ---------------------------
# 13) /mega_summary_from_clusters
# ---------------------------
class MegaSummarizeRequest(BaseModel):
    request_id: str
    cluster_summaries: Dict[str, constr(min_length=1)]

@app.post("/mega_summary_from_clusters")
def mega_summary_from_clusters(payload: MegaSummarizeRequest):
    processed_at = now_iso()

    combined = " ".join(payload.cluster_summaries.values())
    mega_summary = combined[:6000]

    doc = {
        "request_id": payload.request_id,
        "mega_summary": mega_summary,
        "cluster_ids": list(payload.cluster_summaries.keys()),
        "cluster_count": len(payload.cluster_summaries),
        "processed_at": processed_at,
    }

    store_doc("mega_summaries", dict(doc), doc_id=payload.request_id)

    return doc


# ---------------------------
# ARTICLES
# ---------------------------
@app.get("/articles")
def list_articles(limit: int = 100):
    res = client.search(index="articles", body={"size": limit, "query": {"match_all": {}}})
    return [hit["_source"] for hit in res["hits"]["hits"]]

@app.get("/articles/{article_id}")
def get_article(article_id: str):
    try:
        res = client.get(index="articles", id=article_id)
        return res["_source"]
    except Exception:
        raise HTTPException(status_code=404, detail="Article not found")

@app.post("/articles")
def post_article(payload: dict):
    require_fields(payload, ["id", "body"])
    return ingest("articles", payload, doc_id=payload["id"])

# ---------------------------
# LLM BATCH REQUESTS
# ---------------------------
@app.post("/llm/batch")
def post_llm_batch(payload: dict):
    require_fields(payload, ["request_id"])
    if exists("llm_batch_requests", "request_id", payload["request_id"]):
        raise HTTPException(status_code=409, detail="request_id already exists")
    return ingest("llm_batch_requests", payload)

@app.get("/llm/batch/{request_id}")
def get_llm_batch(request_id: str):
    res = client.search(index="llm_batch_requests", body={"query": {"match": {"request_id": request_id}}})
    hits = res["hits"]["hits"]
    if not hits:
        raise HTTPException(status_code=404, detail="Batch request not found")
    return hits[0]["_source"]

# ---------------------------
# BATCH SUMMARIES
# ---------------------------
@app.post("/llm/batch_summary")
def post_batch_summary(payload: dict):
    require_fields(payload, ["request_id", "summary_type", "final_summary"])
    if exists("batch_summaries", "request_id", payload["request_id"]):
        raise HTTPException(status_code=409, detail="Summary already exists for this request_id")
    return ingest("batch_summaries", payload)

# ---------------------------
# CHUNK SUMMARIES
# ---------------------------
@app.post("/llm/chunk_summary")
def post_chunk_summary(payload: dict):
    require_fields(payload, ["request_id", "summary"])
    return ingest("chunk_summaries", payload)

# ---------------------------
# EVALUATIONS (legacy)
# ---------------------------
@app.post("/llm/evaluation")
def post_evaluation(payload: dict):
    require_fields(payload, ["request_id"])
    return ingest("evaluations", payload)

# ---------------------------
# NEWS CLUSTER SUMMARIES (legacy)
# ---------------------------
@app.post("/news_cluster_summary")
def post_news_cluster_summary(payload: dict):
    require_fields(payload, ["request_id", "summary_type", "topic_summary", "cluster_id"])
    return ingest("news_cluster_summaries", payload)

@app.get("/news_cluster_summary/{request_id}")
def get_news_cluster_summary(request_id: str):
    res = client.search(index="news_cluster_summaries", body={"query": {"match": {"request_id": request_id}}})
    hits = res["hits"]["hits"]
    if not hits:
        raise HTTPException(status_code=404, detail="Cluster summary not found")
    return [h["_source"] for h in hits]

@app.post("/news_cluster_summaries/_search")
def search_news_cluster_summaries(query: dict):
    return client.search(index="news_cluster_summaries", body=query)

# ---------------------------
# ARTICLES REQUEST LOGS
# ---------------------------
@app.post("/articles_request")
def post_articles_request(payload: dict):
    require_fields(payload, ["request_id", "source", "endpoint", "http_method", "status"])
    return ingest("articles_request", payload)

@app.get("/articles_request/{request_id}")
def get_articles_request(request_id: str):
    res = client.search(
        index="articles_request",
        body={
            "query": {"term": {"request_id": request_id}},
            "sort": [{"created_at": {"order": "desc"}}],
        },
    )
    hits = res["hits"]["hits"]
    if not hits:
        raise HTTPException(status_code=404, detail="Request log not found")
    return [h["_source"] for h in hits]

@app.get("/articles_request")
def list_articles_requests(limit: int = 20):
    res = client.search(
        index="articles_request",
        body={"size": limit, "sort": [{"created_at": {"order": "desc"}}], "query": {"match_all": {}}},
    )
    return [h["_source"] for h in res["hits"]["hits"]]
