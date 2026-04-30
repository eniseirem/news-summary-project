# Testing Guide: Running Ollama, LLaMA, and Testing Endpoints

Complete guide for setting up and testing the LLM Processing Pipeline API.

---

## Prerequisites

- Python 3.10+ with virtual environment activated
- Ollama installed and accessible
- LLaMA 3.2 3B model pulled
- All dependencies installed (`pip install -r requirements.txt`)

---

## Step 1: Start Ollama Service (Keep Running)

Open **Terminal 1** and run:

```bash
# Start Ollama service (runs in foreground, keep this terminal open)
ollama serve
```

**Expected output:**
```
time=2025-12-05T... level=INFO msg="ollama server is running"
```

**Note:** 
- Keep this terminal window open
- Ollama will run on `http://localhost:11434` by default
- If you see "address already in use", Ollama is already running (this is fine!)

**Verify Ollama is running:**
```bash
curl http://localhost:11434/api/tags
```
Should return JSON with available models.

---

## Step 2: Pull and Verify LLaMA Model (One-Time Setup)

In a **new terminal (Terminal 2)**, pull the required model:

```bash
# Pull the LLaMA 3.2 3B model (as configured in llama3.yaml)
ollama pull llama3.2:3b

# Verify it's available
ollama list
```

You should see `llama3.2:3b` in the list.

**Optional:** Test the model directly:
```bash
ollama run llama3.2:3b "Hello, can you summarize this?"
```

**Note:** You only need to pull the model once. After that, you can close Terminal 2.

---

## Step 3: Start FastAPI Server (Keep Running)

In **Terminal 3**, start your FastAPI server:

```bash
# Navigate to project root
cd /Users/ajocard/AbbyDevelopments/cswspws25

# Activate virtual environment
source .venv/bin/activate

# Set Python path
export PYTHONPATH=src

# Navigate to src directory
cd src

# Start FastAPI server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Note:** 
- Keep this terminal open
- The API will be available at `http://localhost:8000`
- Server will auto-reload when you save code changes

**Verify it's running:**
- Open browser: `http://localhost:8000/docs` (FastAPI Swagger UI)
- Or test: `curl http://localhost:8000`

---

## Step 4: Test in Postman

### Endpoint: `/summarize_clustered`

**Request Details:**
- **Method:** `POST`
- **URL:** `http://localhost:8000/summarize_clustered`
- **Headers:**
  ```
  Content-Type: application/json
  ```

**Request Body Example:**

```json
{
  "request_id": "test_001",
  "filters_used": {},
  "articles": [
    {
      "url": "https://www.theguardian.com/world/2025/nov/29/israel-has-de-facto-state-policy-of-organised-torture-says-un-report",
      "title": "Israel has 'de facto state policy' of organised torture, says UN report",
      "body": "Israel has \"a de facto state policy of organised and widespread torture\", according to a UN report covering the past two years, which also raised concerns about the impunity of Israeli security forces for war crimes. The UN committee on torture expressed \"deep concern over allegations of repeated severe beatings, dog attacks, electrocution, waterboarding, use of prolonged stress positions [and] sexual violence\". The report, published on Friday as part of the committee's regular monitoring of countries that have signed the UN convention against torture, also said Palestinian detainees were humiliated by \"being made to act like animals or being urinated on\", were systematically denied medical care and subject to excessive use of restraints, \"in some cases resulting in amputation\".",
      "language": "en",
      "source": "Guardian",
      "published_at": "2025-11-29T13:18:04Z",
      "category": "world"
    },
    {
      "url": "https://www.theguardian.com/world/2025/nov/29/donald-trump-venezuela-airspace-closure",
      "title": "Donald Trump says airspace above and around Venezuela is closed",
      "body": "Donald Trump said on Saturday that the airspace above and surrounding Venezuela is to be closed in its entirety. Trump, in a Truth Social post said: \"To all Airlines, Pilots, Drug Dealers, and Human Traffickers, please consider THE AIRSPACE ABOVE AND SURROUNDING VENEZUELA TO BE CLOSED IN ITS ENTIRETY.\" Venezuela's communications ministry, which handles all press inquiries for the government, did not immediately reply to a request for comment on Trump's post.",
      "language": "en",
      "source": "Guardian",
      "published_at": "2025-11-29T14:55:22Z",
      "category": "world"
    }
  ]
}
```

**Expected Response:**

```json
{
  "request_id": "test_001",
  "summary_type": "clustered_summary",
  "cluster_count": 2,
  "clusters": [
    {
      "cluster_id": 0,
      "topic_label": "UN Report Israel Torture",
      "category": "Global Politics",
      "topic_summary": "A UN report has documented widespread torture allegations against Israel...",
      "articles": [
        {
          "url": "https://www.theguardian.com/world/2025/nov/29/israel-has-de-facto-state-policy-of-organised-torture-says-un-report",
          "title": "Israel has 'de facto state policy' of organised torture, says UN report"
        }
      ]
    },
    {
      "cluster_id": 1,
      "topic_label": "Trump Venezuela Airspace",
      "category": "Global Politics",
      "topic_summary": "Donald Trump announced the closure of airspace above and around Venezuela...",
      "articles": [
        {
          "url": "https://www.theguardian.com/world/2025/nov/29/donald-trump-venezuela-airspace-closure",
          "title": "Donald Trump says airspace above and around Venezuela is closed"
        }
      ]
    }
  ],
  "mega_summary": "This is a global summary combining all cluster summaries into one coherent overview of the news briefing...",
  "processed_at": "2025-11-29T15:30:00.000000"
}
```

**Response Fields:**
- `clusters`: Array of per-cluster summaries (one summary per topic cluster)
- `mega_summary`: Global summary combining all cluster summaries
- `cluster_count`: Number of clusters detected
- `summary_type`: Always "clustered_summary"

---

## Other Available Endpoints

### `/cluster_summary`
- **Purpose:** Cluster articles and return per-cluster summaries with keyword metadata
- **Request format:** Same as `/summarize_clustered`
- **Response includes:** LDA and TF-IDF keywords per cluster
- **URL:** `http://localhost:8000/cluster_summary`

### `/summarize_batch`
- **Purpose:** Generate a single combined summary from all articles (no clustering)
- **Request format:** Same article structure
- **Response:** Single `final_summary` field
- **URL:** `http://localhost:8000/summarize_batch`

### `/summarize_with_style`
- **Purpose:** Generate summaries with specific writing styles and formats
- **Additional request fields:** `writing_style`, `output_format`
- **URL:** `http://localhost:8000/summarize_with_style`

---

## Troubleshooting

### Ollama Issues

**Ollama not responding:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve

# If already running but not responding, restart
pkill ollama
ollama serve
```

**Model not found:**
```bash
# Pull the model
ollama pull llama3.2:3b

# Verify it's available
ollama list
```

**Port 11434 already in use:**
- This means Ollama is already running (this is fine!)
- Verify with: `curl http://localhost:11434/api/tags`
- No action needed

---

### FastAPI Issues

**Port 8000 already in use:**
```bash
# Find what's using port 8000
lsof -ti:8000

# Kill the process(es)
kill -9 $(lsof -ti:8000)

# Then start the server again
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Python path errors:**
```bash
# Verify PYTHONPATH is set
echo $PYTHONPATH  # Should output: src

# If not set, export it
export PYTHONPATH=src
```

**Virtual environment not activated:**
```bash
# Check if venv is active
which python  # Should show path to .venv/bin/python

# If not, activate it
source .venv/bin/activate
```

**Import errors:**
```bash
# Make sure you're in the src directory
cd /Users/ajocard/AbbyDevelopments/cswspws25/src

# Verify dependencies are installed
pip install -r ../requirements.txt
```

**Connection refused:**
```bash
# Verify Ollama is on port 11434
lsof -i :11434

# Verify FastAPI is on port 8000
lsof -i :8000
```

---

## Quick Reference Commands

### Terminal 1 (Ollama):
```bash
ollama serve
```

### Terminal 2 (One-time model setup):
```bash
ollama pull llama3.2:3b
ollama list
```

### Terminal 3 (FastAPI):
```bash
cd /Users/ajocard/AbbyDevelopments/cswspws25
source .venv/bin/activate
export PYTHONPATH=src
cd src
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Kill processes on ports:
```bash
# Kill port 8000
kill -9 $(lsof -ti:8000)

# Kill port 11434 (Ollama)
pkill ollama
```

---

## Processing Times

- **Small batches (2-5 articles):** 10-30 seconds
- **Medium batches (5-15 articles):** 30-60 seconds
- **Large batches (15+ articles):** 60-120+ seconds

Processing time depends on:
- Number of articles
- Number of clusters detected
- Length of article content
- LLaMA model response time

---

## Important Notes

- **Ollama** must stay running (Terminal 1) - keep the terminal open
- **FastAPI** must stay running (Terminal 3) - keep the terminal open
- **LLaMA model** only needs to be pulled once (Terminal 2 can be closed after pulling)
- The model will be loaded automatically when first requested
- FastAPI server auto-reloads when you save code changes (thanks to `--reload` flag)
- Use `Ctrl+C` in the terminal to stop either service

---

## API Documentation

Interactive API documentation is available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

These provide interactive testing interfaces where you can:
- See all available endpoints
- View request/response schemas
- Test endpoints directly in the browser
- See example requests and responses
