import requests
import time
import copy
import json
import os
from requests.auth import HTTPBasicAuth

API_BASE_URL = "http://localhost:8002"
OPENSEARCH_URL = "https://localhost:9200"
OS_AUTH = HTTPBasicAuth("admin", "admin")

def wait_for_url(url, timeout_seconds=60, verify=False):
    print(f"Waiting for {url} ...")
    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            r = requests.get(url, auth=OS_AUTH, verify=verify, timeout=3)
            if r.status_code in (200, 401, 403):  # 401/403 still means service alive
                print(f"{url} is reachable (status {r.status_code})")
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"Timeout waiting for {url}")
    return False

def index_exists(index_name):
    url = f"{OPENSEARCH_URL.rstrip('/')}/{index_name}"
    try:
        r = requests.get(url, auth=OS_AUTH, verify=False, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def create_index_in_opensearch(index_name, mapping):
    """
    Create index with sensible settings. If mapping creation fails due to dense_vector
    not supported, retry with centroid_embedding as object (safe fallback).
    """
    url = f"{OPENSEARCH_URL.rstrip('/')}/{index_name}"
    if index_exists(index_name):
        print(f"Index {index_name} already exists, skipping creation.")
        return True

    # The mapping file can contain settings and mappings
    body = mapping

    print(f"Creating index {index_name} at {url}")
    try:
        resp = requests.put(url, json=body, auth=OS_AUTH, verify=False, timeout=10)
        if resp.status_code in (200, 201):
            print(f"Index {index_name} created/acknowledged.")
            return True
        else:
            # If OpenSearch complains about knn_vector (plugin missing), try safe fallback
            text = resp.text.lower() if resp.text else ""
            print(f"Warning: creating index {index_name} returned {resp.status_code}: {resp.text}")
            if "knn_vector" in text or "dense_vector" in text:
                print("knn_vector/dense_vector not supported on this OpenSearch instance – retrying with fallback mapping.")
                safe_body = copy.deepcopy(body)
                props = safe_body.get("mappings", {}).get("properties", {})

                if "centroid_embedding" in props and "type" in props["centroid_embedding"]:
                    props["centroid_embedding"] = {"type": "object", "enabled": False}
                if "embedding_knn" in props and "type" in props["embedding_knn"]:
                    props["embedding_knn"] = {"type": "object", "enabled": False}

                # Remove knn settings if they exist
                if "settings" in safe_body and "index" in safe_body["settings"]:
                    safe_body["settings"]["index"].pop("knn", None)

                resp2 = requests.put(url, json=safe_body, auth=OS_AUTH, verify=False, timeout=10)
                if resp2.status_code in (200, 201):
                    print(f"Index {index_name} created with fallback mapping.")
                    return True
                else:
                    print(f"Fallback mapping also failed: {resp2.status_code}: {resp2.text}")
            return False
    except Exception as e:
        print(f"Error creating index {index_name}: {e}")
        return False

def index_document(index_name, doc_id, doc):
    url = f"{OPENSEARCH_URL.rstrip('/')}/{index_name}/_doc/{doc_id}"
    try:
        resp = requests.put(url, json=doc, auth=OS_AUTH, verify=False, timeout=10)
        if resp.status_code not in (200,201):
            print(f"Indexing doc {doc_id} into {index_name} returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error indexing doc {doc_id} into {index_name}: {e}")

def main():
    # wait for OpenSearch and API
    if not wait_for_url(OPENSEARCH_URL):
        print("OpenSearch did not come up, aborting.")
        return
    if not wait_for_url(API_BASE_URL):
        print("API did not come up, aborting.")
        return

    # --- Load Mappings from JSON files ---
    indices_to_create = ["articles", "clusters", "news_cluster_summaries"]
    indices_with_mappings = {}
    script_dir = os.path.dirname(__file__)

    for index_name in indices_to_create:
        try:
            mapping_path = os.path.join(script_dir, '..', 'indices', f'{index_name}.json')
            with open(mapping_path, 'r', encoding='utf-8') as f:
                indices_with_mappings[index_name] = json.load(f)
            print(f"Successfully loaded mapping for index '{index_name}'.")
        except FileNotFoundError:
            print(f"ERROR: Mapping file for index '{index_name}' not found at {mapping_path}. The index will not be created.")
        except json.JSONDecodeError:
            print(f"ERROR: Could not decode JSON from mapping file for '{index_name}'.")
        except Exception as e:
            print(f"An unexpected error occurred while loading mapping for '{index_name}': {e}")

    # Create indices using loaded mappings
    for idx, mapping_body in indices_with_mappings.items():
        created = create_index_in_opensearch(idx, mapping_body)
        if not created:
            print(f"Failed to create index {idx}. Continue to next index.")

    # Ingest sample documents directly into OpenSearch so categories are immediately available
    sample_articles = [
        {"id": "art_tech_001", "title": "New AI Model Released", "body": "A new AI model promises to revolutionize the industry.", "language": "en", "source": "TechCrunch", "published_at": "2023-10-27T10:00:00Z"},
        {"id": "art_tech_002", "title": "Startup raises funding for AI chip", "body": "A small startup received funding for a novel AI chip architecture.", "language": "en", "source": "VentureBeat", "published_at": "2023-10-26T08:30:00Z"},
        {"id": "art_pol_001", "title": "Global Summit Concludes", "body": "Leaders from around the world met to discuss climate change.", "language": "en", "source": "Reuters", "published_at": "2023-10-27T12:00:00Z"},
        {"id": "art_eco_001", "title": "Wirtschaftsindikatoren zeigen Wachstum", "body": "Die neuesten Wirtschaftsdaten deuten auf ein starkes Quartal hin.", "language": "de", "source": "Handelsblatt", "published_at": "2023-10-26T09:00:00Z"},
        {"id": "art_sports_001", "title": "Local Team Wins Championship", "body": "An underdog team secured the national title in a thrilling match.", "language": "en", "source": "ESPN", "published_at": "2023-10-25T18:00:00Z"},
    ]
    for a in sample_articles:
        index_document("articles", a["id"], a)

    # Load sample news_cluster_summaries from JSON file
    cluster_summaries = []
    try:
        # Construct path relative to this script's location
        script_dir = os.path.dirname(__file__)
        json_path = os.path.join(script_dir, 'sample_data', 'news_cluster_summaries.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            cluster_summaries = json.load(f)
        print(f"Successfully loaded {len(cluster_summaries)} cluster summaries from JSON.")
    except FileNotFoundError:
        print(f"ERROR: sample_data/news_cluster_summaries.json not found. No sample summaries will be indexed.")
    except json.JSONDecodeError:
        print(f"ERROR: Could not decode sample_data/news_cluster_summaries.json. Check for syntax errors.")
    except Exception as e:
        print(f"An unexpected error occurred while reading the summaries JSON: {e}")


    for c in cluster_summaries:
        index_document("news_cluster_summaries", c["id"], c)

    print("\nInfrastructure setup complete. News categories should now be queryable from OpenSearch.")

if __name__ == "__main__":
    main()
