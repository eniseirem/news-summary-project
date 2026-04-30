import streamlit as st
import requests
import sys
from requests.auth import HTTPBasicAuth
from config import OPENSEARCH_URLS, OPENSEARCH_USER, OPENSEARCH_PASS, FALLBACK_CATEGORIES

# Build list to try: each endpoint first HTTPS, then HTTP (for Docker OpenSearch without TLS)
def _opensearch_urls_to_try():
    seen = set()
    urls = []
    for u in OPENSEARCH_URLS:
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
        # If this was HTTPS, add HTTP fallback for same host (in case OpenSearch uses HTTP)
        if u.startswith("https://"):
            host_rest = u[8:].split("/", 1)[0]  # e.g. "opensearch:9200"
            http_url = "http://" + host_rest
            if http_url not in seen:
                seen.add(http_url)
                urls.append(http_url)
    return urls

@st.cache_data(ttl=300)
def fetch_categories_from_opensearch():
    """Fetch unique categories from clusters index"""

    errors = []
    urls_to_try = _opensearch_urls_to_try()

    for base_url in urls_to_try:
        try:
            query = {
                "size": 0,
                "query": {
                    "range": {"processed_at": {"gte": "now-30d"}}
                },
                "aggs": {
                    "unique_categories": {
                        "terms": {
                            "field": "category",
                            "size": 100
                        }
                    }
                }
            }

            url = f"{base_url}/clusters/_search"
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
                    # Index exists but is empty (no clusters yet) – use fallback so the UI still works
                    print(f"[DEBUG] OpenSearch reachable at {base_url} but clusters index has no categories; using fallback list.", file=sys.stderr)
                    return sorted(FALLBACK_CATEGORIES), base_url, None
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
    """Fetch subcategories (topic_labels) for a given category from cluster_summaries"""
    
    if not opensearch_url:
        return []
    
    try:
        cluster_query = {
            "size": 1000,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category": category}},
                        {"range": {"processed_at": {"gte": "now-30d"}}}
                    ]
                }
            },
            "_source": ["cluster_id"]
        }
        
        url = f"{opensearch_url}/clusters/_search"
        response = requests.post(
            url,
            json=cluster_query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        cluster_ids = [str(hit["_source"]["cluster_id"]) for hit in data.get("hits", {}).get("hits", [])]
        
        if not cluster_ids:
            return []
        
        summary_query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"cluster_id": cluster_ids}},
                        {"range": {"processed_at": {"gte": "now-30d"}}}
                    ]
                }
            },
            "aggs": {
                "unique_topics": {
                    "terms": {
                        "field": "topic_label.keyword",
                        "size": 100
                    }
                }
            }
        }
        
        url = f"{opensearch_url}/cluster_summaries/_search"
        response = requests.post(
            url,
            json=summary_query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            buckets = data.get("aggregations", {}).get("unique_topics", {}).get("buckets", [])
            topics = [bucket["key"] for bucket in buckets if bucket.get("key") and bucket["key"].strip()]
            return sorted(topics)
    
    except Exception as e:
        print(f"[ERROR] Subcategory fetch error: {str(e)}", file=sys.stderr)
    
    return []


def fetch_clusters_from_opensearch(category, subcategory, opensearch_url, language=None):
    """
    Fetch clusters for a given category by:
    1. Getting cluster data from clusters index (filtered by category)
    2. Getting ALL summaries from cluster_summaries index
    3. Matching by string conversion of cluster_id
    4. Getting mega summary from mega_summaries index
    5. Getting articles from articles index
    """

    if not opensearch_url:
        print("[ERROR] No opensearch_url provided", file=sys.stderr)
        return [], None

    try:
        print(f"[DEBUG] Fetching clusters for category='{category}', subcategory='{subcategory}', language={language}", file=sys.stderr)
        
        cluster_query = {
            "size": 1000,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category": category}},
                        {"range": {"processed_at": {"gte": "now-30d"}}}
                    ]
                }
            },
            "_source": ["cluster_id", "article_ids", "article_count", "topic_label", "processed_at"],
            "sort": [{"processed_at": {"order": "desc"}}]
        }

        url = f"{opensearch_url}/clusters/_search"
        print(f"[DEBUG] Querying clusters index: {url}", file=sys.stderr)
        
        response = requests.post(
            url,
            json=cluster_query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )

        print(f"[DEBUG] Clusters response status: {response.status_code}", file=sys.stderr)
        
        if response.status_code != 200:
            print(f"[ERROR] Clusters fetch HTTP {response.status_code}", file=sys.stderr)
            print(f"[ERROR] Response body: {response.text[:500]}", file=sys.stderr)
            return [], None

        cluster_data = response.json()
        cluster_hits = cluster_data.get("hits", {}).get("hits", [])
        total_hits = cluster_data.get("hits", {}).get("total", {})
        
        print(f"[DEBUG] Total clusters found: {total_hits}", file=sys.stderr)
        print(f"[DEBUG] Returned hits: {len(cluster_hits)}", file=sys.stderr)
        
        if not cluster_hits:
            print(f"[INFO] No clusters found for category: {category}", file=sys.stderr)
            return [], None

        cluster_info = {}
        all_cluster_ids_str = []
        
        for hit in cluster_hits:
            source = hit.get("_source", {})
            cluster_id = source.get("cluster_id")
            
            if cluster_id is not None:
                cluster_id_str = str(cluster_id)
                topic_label_src = source.get("topic_label", "")
                cluster_info[cluster_id_str] = {
                    "article_ids": source.get("article_ids", []),
                    "article_count": source.get("article_count", 0),
                    "topic_label": topic_label_src,
                    "processed_at": source.get("processed_at", "")
                }
                all_cluster_ids_str.append(cluster_id_str)

        # --- Fetch keywords for these clusters (keywords index uses article_ids == cluster_id) ---
        try:
            keywords_by_cluster = fetch_keywords_for_clusters(opensearch_url, all_cluster_ids_str)
        except NameError:
            # Helper may not exist in older deployments; fall back gracefully
            keywords_by_cluster = {}
        except Exception as e:
            print(f"[ERROR] Keyword fetch error: {e}", file=sys.stderr)
            keywords_by_cluster = {}

        summary_query = {
            "size": 1000,
            "query": {
                "range": {"processed_at": {"gte": "now-30d"}}
            },
            "sort": [{"processed_at": {"order": "desc"}}]
        }

        url = f"{opensearch_url}/cluster_summaries/_search"
        print(f"[DEBUG] Querying cluster_summaries index for ALL summaries", file=sys.stderr)
        
        response = requests.post(
            url,
            json=summary_query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )

        print(f"[DEBUG] Cluster summaries response status: {response.status_code}", file=sys.stderr)

        summaries_by_cluster = {}
        request_ids = set()
        
        if response.status_code == 200:
            summary_data = response.json()
            summary_hits = summary_data.get("hits", {}).get("hits", [])
            print(f"[DEBUG] Found {len(summary_hits)} total summaries", file=sys.stderr)
            
            matched_count = 0
            for hit in summary_hits:
                source = hit.get("_source", {})
                cluster_id = str(source.get("cluster_id", ""))
                request_id = source.get("request_id")
                
                if cluster_id in all_cluster_ids_str:
                    matched_count += 1
                    if request_id:
                        request_ids.add(request_id)
                    
                    topic_label = source.get("topic_label", "")
                    if subcategory and topic_label != subcategory:
                        continue
                    
                    summaries_by_cluster[cluster_id] = {
                        "request_id": request_id,
                        "topic_label": topic_label,
                        "summary": source.get("summary", ""),
                        "summary_translated": source.get("summary_translated"),
                        "summary_translated_language": source.get("summary_translated_language"),
                        "processed_at": source.get("processed_at", ""),
                        "styled_summary": source.get("styled_summary"),
                        "style_meta": source.get("style_meta", {})
                    }
            
            print(f"[DEBUG] Matched {matched_count} summaries to cluster_ids", file=sys.stderr)
            print(f"[DEBUG] After subcategory filter: {len(summaries_by_cluster)} summaries", file=sys.stderr)
        else:
            print(f"[WARNING] Cluster summaries fetch failed: {response.status_code}", file=sys.stderr)

        print(f"[DEBUG] Request IDs found: {request_ids}", file=sys.stderr)

        mega_summary_data = None
        mega_query = {
            "size": 1,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category_name": category}},
                        {"range": {"processed_at": {"gte": "now-30d"}}}
                    ]
                }
            },
            "sort": [{"processed_at": {"order": "desc"}}]
        }

        url = f"{opensearch_url}/mega_summaries/_search"
        print(f"[DEBUG] Querying mega_summaries index for category: {category}", file=sys.stderr)
        
        response = requests.post(
            url,
            json=mega_query,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            verify=False,
            timeout=5
        )

        print(f"[DEBUG] Mega summaries response status: {response.status_code}", file=sys.stderr)

        if response.status_code == 200:
            mega_data = response.json()
            hits = mega_data.get("hits", {}).get("hits", [])
            if hits:
                source = hits[0].get("_source", {})
                mega_summary_data = {
                    "original": source.get("mega_summary"),
                    "translated": source.get("mega_summary_translated"),
                    "translated_language": source.get("mega_summary_translated_language"),
                    "request_id": source.get("request_id")
                }
                print(f"[DEBUG] Found mega summary for category: {category}", file=sys.stderr)
            else:
                print(f"[DEBUG] No mega summary found for category: {category}", file=sys.stderr)

        all_article_ids = []
        for info in cluster_info.values():
            all_article_ids.extend(info.get("article_ids", []))

        all_article_ids = list(set(all_article_ids))
        print(f"[DEBUG] Total unique article IDs to fetch: {len(all_article_ids)}", file=sys.stderr)

        articles_by_id = {}
        if all_article_ids:
            articles_query = {
                "size": 10000,
                "query": {
                    "terms": {"id": all_article_ids}
                },
                "_source": ["id", "title", "source", "url", "published_at"]
            }

            url = f"{opensearch_url}/articles/_search"
            print(f"[DEBUG] Querying articles index", file=sys.stderr)
            
            response = requests.post(
                url,
                json=articles_query,
                auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
                verify=False,
                timeout=10
            )

            print(f"[DEBUG] Articles response status: {response.status_code}", file=sys.stderr)

            if response.status_code == 200:
                articles_data = response.json()
                article_hits = articles_data.get("hits", {}).get("hits", [])
                print(f"[DEBUG] Found {len(article_hits)} articles", file=sys.stderr)
                
                for hit in article_hits:
                    source = hit.get("_source", {})
                    article_id = source.get("id")
                    if article_id:
                        articles_by_id[article_id] = {
                            "id": article_id,
                            "title": source.get("title", "No title"),
                            "source": source.get("source", "Unknown"),
                            "url": source.get("url"),
                            "published_at": source.get("published_at")
                        }

        clusters = []
        for cluster_id_str, info in cluster_info.items():
            summary_data = summaries_by_cluster.get(cluster_id_str, {})
            
            article_ids = info.get("article_ids", [])
            articles = [articles_by_id[aid] for aid in article_ids if aid in articles_by_id]

            if not summary_data and not articles:
                continue
            
            if subcategory:
                topic_label = summary_data.get("topic_label", "")
                if topic_label != subcategory:
                    continue

            topic_label = summary_data.get("topic_label") or info.get("topic_label", "")

            cluster = {
                "cluster_id": cluster_id_str,
                "request_id": summary_data.get("request_id"),
                "topic_label": topic_label,
                "topic_summary": summary_data.get("summary", ""),
                "summary_translated": summary_data.get("summary_translated"),
                "summary_translated_language": summary_data.get("summary_translated_language"),
                "styled_summary": summary_data.get("styled_summary"),
                "style_meta": summary_data.get("style_meta", {}),
                "articles": articles,
                "article_count": len(articles),
                "processed_at": summary_data.get("processed_at") or info.get("processed_at", ""),
                # Attach cluster-specific keywords (may be empty list)
                "keywords": keywords_by_cluster.get(cluster_id_str, [])
            }
            clusters.append(cluster)

        clusters.sort(key=lambda x: x.get("processed_at", ""), reverse=True)

        print(f"[INFO] Returning {len(clusters)} clusters with {len(articles_by_id)} total articles", file=sys.stderr)
        return clusters, mega_summary_data

    except Exception as e:
        print(f"[ERROR] Cluster fetch error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()

    return [], None


def fetch_keywords_from_opensearch(opensearch_url):
    """
    Legacy helper: fetch ALL distinct keywords from keywords index.
    Kept for backwards compatibility, but prefer fetch_keywords_for_clusters.
    """
    try:
        url = f"{opensearch_url}/keywords/_search"
        query = {
            "size": 1000,
            "_source": ["tfidf_keywords", "lda_keywords"]
        }

        r = requests.post(
            url,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
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
        print(f"[KEYWORDS ERROR] {e}", file=sys.stderr)
        return []


def fetch_keywords_for_clusters(opensearch_url, cluster_ids):
    """
    Fetch keywords per cluster from keywords index.

    NOTE: In the keywords index, the field `article_ids` actually stores the `cluster_id`.
    We therefore query by `article_ids` and map back to cluster_id strings.

    Returns:
        dict[str, list[str]]: {cluster_id: [keywords...]}
    """
    if not opensearch_url or not cluster_ids:
        return {}

    try:
        # Ensure all IDs are strings
        cluster_ids = [str(cid) for cid in cluster_ids if cid is not None]
        if not cluster_ids:
            return {}

        url = f"{opensearch_url}/keywords/_search"
        query = {
            "size": 1000,
            "query": {
                "terms": {
                    "article_ids": cluster_ids
                }
            },
            "_source": ["article_ids", "tfidf_keywords", "lda_keywords"]
        }

        r = requests.post(
            url,
            auth=HTTPBasicAuth(OPENSEARCH_USER, OPENSEARCH_PASS),
            headers={"Content-Type": "application/json"},
            json=query,
            verify=False,
            timeout=5
        )

        if r.status_code != 200:
            print(f"[KEYWORDS ERROR] HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
            return {}

        data = r.json()
        by_cluster = {}

        for hit in data.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            # article_ids is misnamed and actually stores cluster_id(s)
            ids = src.get("article_ids", [])
            if isinstance(ids, str):
                ids = [ids]

            hit_keywords = set()
            for k in src.get("tfidf_keywords", []):
                hit_keywords.add(k)
            for k in src.get("lda_keywords", []):
                hit_keywords.add(k)

            if not hit_keywords:
                continue

            for cid in ids:
                cid_str = str(cid)
                if cid_str not in by_cluster:
                    by_cluster[cid_str] = set()
                by_cluster[cid_str].update(hit_keywords)

        # Convert sets to sorted lists
        result = {cid: sorted(list(kw_set)) for cid, kw_set in by_cluster.items()}

        return result

    except Exception as e:
        print(f"[KEYWORDS ERROR] fetch_keywords_for_clusters: {e}", file=sys.stderr)
        return {}
