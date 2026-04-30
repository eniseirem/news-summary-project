After a successful setup, the following services will be available:

- **OpenSearch**: https://localhost:9200  
- **Dashboard (Streamlit)**: http://localhost:8501  
- **SoPro API (FastAPI)**: http://localhost:8002  

### 1. Install Docker Desktop

>> Docker must be running before continuing.

docker --version


SetupOpensearchLocal
├─ docker-compose.yml
├─ api/
│  ├─ api.py
│  └─ requirements.txt
├─ dashboard/
│  ├─ app.py
│  └─ requirements.txt
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
│  ├─ restore_indices.cmd
│  └─ requirements.txt
└─ README.md

1.
in cmd open SetupOpensearchLocal

2. Clean Start
docker compose down -v --remove-orphans
docker compose up -d --build

This may take 1–3 minutes

3. Verifying everything worked
curl -k -u admin:admin https://localhost:9200
If you receive JSON containing cluster_name, OpenSearch is ready.

4. Set up Indices
cd scripts
pip install -r requirements.txt
python setup_infra.py

5. Verify services
docker ps

The following containers must be running:

opensearch

opensearch-python-api

dashboard



Dashboard should be ready: http://localhost:8501

Create a Test Article
curl -X POST http://localhost:8002/articles -H "Content-Type: application/json" -d "{\"id\":\"test_1\",\"title\":\"Test Article\",\"body\":\"This is a test body\",\"language\":\"en\"}"


Fetch the article
curl http://localhost:8002/articles/test_1
