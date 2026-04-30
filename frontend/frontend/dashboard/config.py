import os

# CONFIGURATION
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://n8n:5678/webhook/cluster-summary"
)
N8N_STYLE_WEBHOOK_URL = os.getenv(
    "N8N_STYLE_WEBHOOK_URL",
    "http://n8n:5678/webhook/style"
)
# OpenSearch configuration (try HTTPS first, then HTTP for dev/Docker without TLS)
OPENSEARCH_URLS = [
    "https://opensearch:9200",
    "https://host.docker.internal:9200",
    "https://localhost:9200",
    "http://opensearch:9200",
    "http://host.docker.internal:9200",
    "http://localhost:9200",
]
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASS", "admin")

# Fallback categories 
FALLBACK_CATEGORIES = ['General News', 'Global Politics', 'Economics', 'Sports', 'Events']
