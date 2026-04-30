import streamlit as st
import requests
import sys
from requests.auth import HTTPBasicAuth
from config import OPENSEARCH_URLS, OPENSEARCH_USER, OPENSEARCH_PASS

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_categories_from_opensearch():
    """Fetch unique categories from news_cluster_summaries index"""

    errors = []

    for base_url in OPENSEARCH_URLS:
        try:
            query = {
                "size": 0,
                "aggs": {
                    "unique_categories": {
                        "terms": {
                            "field": "category.keyword",   
                            "size": 100
                        }
                    }
                }
            }

            url = f"{base_url}/news_cluster_summaries/_search"
            print(f"[DEBUG] Trying URL: {url}", file=sys.stderr)

            response = requests.post(
                url,
                json=query,
                auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
                verify=False,
                timeout=5
            )

            print(f"[DEBUG] Response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                data = response.json()
                buckets = data.get("aggregations", {}).get("unique_categories", {}).get("buckets", [])
                categories = [bucket["key"] for bucket in buckets if bucket.get("key")]

                if categories:
                    print(f"[DEBUG] Successfully loaded {len(categories)} categories from {base_url}", file=sys.stderr)
                    return sorted(categories), base_url, None
                else:
                    errors.append({"url": base_url, "status": response.status_code, "error": "No categories found in aggregation"})
            else:
                try:
                    text = response.text
                except Exception:
                    text = "<no body>"
                errors.append({"url": base_url, "status": response.status_code, "error": text})

        except Exception as e:
            print(f"[ERROR] {base_url}: {str(e)}", file=sys.stderr)
            errors.append({"url": base_url, "exception": str(e)})
            continue

    print("[WARNING] All OpenSearch URLs failed or returned no categories", file=sys.stderr)
    return [], None, errors


@st.cache_data(ttl=300)
def fetch_subcategories_from_opensearch(category, opensearch_url):
    """Fetch subcategories for a given category"""

    if not opensearch_url:
        return []

    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [{"term": {"category": category}}]   # changed: term on "category"
                }
            },
            "aggs": {
                "unique_subcategories": {
                    "terms": {
                        "field": "subcategory.keyword",   
                        "size": 100
                    }
                }
            }
        }

        url = f"{opensearch_url}/news_cluster_summaries/_search"
        response = requests.post(
            url,
            json=query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            buckets = data.get("aggregations", {}).get("unique_subcategories", {}).get("buckets", [])
            subcategories = [bucket["key"] for bucket in buckets if bucket.get("key") and str(bucket.get("key")).strip()]
            return sorted(subcategories)
        else:
            print(f"[ERROR] Subcategory fetch HTTP {response.status_code} for {opensearch_url}", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Subcategory fetch error: {str(e)}", file=sys.stderr)

    return []


@st.cache_data(ttl=300)
def fetch_clusters_from_opensearch(category, subcategory, opensearch_url, language=None):
    """Fetch clusters for a given category (and optionally subcategory and language)"""

    if not opensearch_url:
        return [], None

    try:
        # Build query
        must_conditions = [{"term": {"category.keyword": category}}]   # changed: use "category"

        if subcategory:
            must_conditions.append({"term": {"subcategory.keyword": subcategory}})  # changed: use "subcategory"

        # changed in language summary adoption
        if language:
            must_conditions.append({
                "bool": {
                    "should": [
                        {
                            "term": {
                                "language": language
                            }
                        },
                        {
                            "term": {
                                "summary_translated_language": language
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            })

        query = {
            "size": 100,
            "query": {
                "bool": {
                    "must": must_conditions
                }
            },
            "sort": [
                {"processed_at": {"order": "desc"}}
            ]
        }

        url = f"{opensearch_url}/news_cluster_summaries/_search"
        response = requests.post(
            url,
            json=query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            clusters = []
            mega_summary_data = None

            for hit in hits:
                source = hit.get("_source", {})

                # Get mega_summary from first cluster (they all have the same one)
                if mega_summary_data is None:
                    mega_summary_data = {
                        "original": source.get("mega_summary"),
                        "translated": source.get("mega_summary_translated"),
                        "translated_language": source.get("summary_translated_language")
                    }
                

                #added following 4 lines +  changed "topic_summary" in clusters.append    
                clusters.append({
                    "cluster_id": source.get("cluster_id"),
                    "id": source.get("id"),
                    "request_id": source.get("request_id"),


                    "topic_summary": source.get("topic_summary", ""),

                    "summary_translated": source.get("summary_translated"),
                    "summary_translated_language": source.get("summary_translated_language"),

                    "topic_label": source.get("topic_label", ""),
                    "articles": source.get("articles", []),
                    "article_count": source.get("article_count", 0),
                    "processed_at": source.get("processed_at", "")
})

            return clusters, mega_summary_data

        else:
            print(f"[ERROR] Cluster fetch HTTP {response.status_code} for {opensearch_url}", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Cluster fetch error: {str(e)}", file=sys.stderr)

    return [], None

@st.cache_data(ttl=300)
def fetch_keywords_from_opensearch(opensearch_url):
    try:
        url = f"{opensearch_url}/keywords/_search"
        query = {
            "size": 100,
            "_source": ["tfidf_keywords", "lda_keywords"]
        }

        r = requests.post(
            url,
            auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            headers={"Content-Type": "application/json"},
            json=query,
            verify=False,
            timeout=5
        )

        if r.status_code != 200:
            return []

        data = r.json()
        keywords = set()

        for hit in data.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            for k in src.get("tfidf_keywords", []):
                keywords.add(k)
            for k in src.get("lda_keywords", []):
                keywords.add(k)

        return sorted(list(keywords))

    except Exception as e:
        print(f"[KEYWORDS ERROR] {e}")
        return []

