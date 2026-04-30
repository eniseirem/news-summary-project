After a successful setup, the following services will be available:

- **OpenSearch**: https://localhost:9200  
- **OpenSearch Dashboards**: http://localhost:5601  
- **SoPro API (FastAPI)**: http://localhost:8002  

### 1. Install Docker Desktop

>> Docker must be running before continuing.

docker --version


SetupOpensearchLocal
├─ docker-compose.yml
├─ api/
│  └─ api.py
├─ indices/
│  ├─ articles.json
│  ├─ clusters.json
│  ├─ cluster_summaries.json
│  ├─ mega_summaries.json
│  ├─ topic_label.json
│  ├─ category_label.json
│  ├─ keywords.json
│  ├─ article_summaries.json
│  ├─ articles_request.json
│  ├─ evaluate_cluster.json
│  ├─ evaluate_mega.json
│  └─ …
├─ scripts/
│  └─ restore_indices.cmd
└─ README.md

1.
in cmd open SetupOpensearchLocal

2. Clean Start
docker compose down -v --remove-orphans
docker compose up -d

This may take 1–3 minutes

3. Verifying everything worked
curl -k -u admin:admin https://localhost:9200
If you receive JSON containing cluster_name, OpenSearch is ready.

4. Set up Indices
cd scripts
restore_indices.cmd

5. Verify services
docker ps

The following containers must be running:

opensearch

opensearch-dashboards

opensearch-python-api



Dashboard should be ready: http://localhost:5601

Create a Test Article
curl -X POST http://localhost:8002/articles ^
  -H "Content-Type: application/json" ^
  -d "{ 
        \"id\": \"test_1\",
        \"title\": \"Test Article\",
        \"body\": \"This is a test body\",
        \"language\": \"en\"
      }"

Fetch the article
curl http://localhost:8002/articles/test_1



