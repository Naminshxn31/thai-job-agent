# 🤖 Thai Job Market AI Agent

> Production-grade LLM Agent for Thailand IT/Data job market intelligence.
> Multi-tool Gemini agent with RAG, FastAPI backend, Streamlit UI, Docker deployment.

---

## 🏗️ Architecture

```
User (Streamlit UI / API)
        │
        ▼
  FastAPI  (/chat, /jobs/*)
        │
        ▼
  JobAgent (Gemini Function Calling)
   ├── tool: job_search       → ChromaDB RAG (semantic search)
   ├── tool: salary_analysis  → ChromaDB RAG (aggregation)
   └── tool: skill_gap_check  → ChromaDB RAG (skill frequency)
        │
        ▼
  ChromaDB (persistent vector store)
  Gemini Embedding API (text-embedding-004)
```

**Key design decisions:**
- Gemini Function Calling (not simple prompt injection) → LLM decides which tool to call
- ChromaDB with cosine similarity → accurate semantic job search
- Pydantic Settings → all config from env, no hardcoded values
- JSON structured logging → ready for log aggregation (Grafana/ELK)
- Session-based memory → multi-turn conversation per user
- Docker + healthcheck → production deploy ready

---

## 🚀 Quick Start

### 1. Setup

```bash
git clone <repo>
cd thai-job-agent

cp .env.example .env
# Edit .env — add GEMINI_API_KEY
# Get free key at: https://aistudio.google.com/apikey

pip install -r requirements.txt
```

### 2. Load job data

```bash
# Synthetic data (no scraping needed — good for demo)
python scripts/load_jobs.py --source synthetic

# Or from your own CSV
python scripts/load_jobs.py --source csv --file data/jobs.csv

# Or scrape (may be blocked)
python scripts/load_jobs.py --source scrape --pages 5
```

### 3. Run locally

```bash
# Terminal 1 — API
uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — UI
streamlit run app/ui/streamlit_app.py
```

Open: http://localhost:8501

### 4. Run with Docker

```bash
docker-compose up --build
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness + readiness |
| POST | `/chat` | Multi-turn agent chat |
| DELETE | `/chat/{session_id}` | Reset conversation |
| POST | `/jobs/search` | Semantic job search |
| POST | `/jobs/salary` | Salary analysis by role |
| POST | `/jobs/skill-gap` | Skill gap analysis |

### Chat example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ML Engineer ที่ Bitkub เงินเดือนประมาณเท่าไหร่?", "session_id": "user-001"}'
```

### Skill gap example

```bash
curl -X POST http://localhost:8000/jobs/skill-gap \
  -H "Content-Type: application/json" \
  -d '{"target_role": "ML Engineer", "current_skills": ["Python", "scikit-learn", "pandas"]}'
```

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 📁 Project Structure

```
thai-job-agent/
├── app/
│   ├── config.py          # Pydantic settings (env-based)
│   ├── logger.py          # JSON structured logging
│   ├── agent/
│   │   └── core.py        # Gemini Function Calling agent
│   ├── api/
│   │   └── main.py        # FastAPI app
│   ├── rag/
│   │   └── retriever.py   # ChromaDB semantic search
│   ├── tools/
│   │   └── job_tools.py   # 3 agent tools + dispatcher
│   └── ui/
│       └── streamlit_app.py
├── scripts/
│   └── load_jobs.py       # Data ingestion pipeline
├── tests/
│   └── test_tools.py      # Pytest unit tests
├── data/chroma/           # Persisted vector store
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 💬 Interview Talking Points

**Q: Why Function Calling instead of just prompt engineering?**
> Function calling gives the LLM a structured contract — it returns a JSON schema call instead of free text. This is more reliable in production because you can validate inputs/outputs, log tool usage, and swap tools without changing prompts. It's also how enterprise LLM orchestration works (LangChain tools, OpenAI function calling).

**Q: How does your RAG work?**
> I embed job descriptions with Gemini's `text-embedding-004` and store vectors in ChromaDB with cosine similarity. At query time, I embed the user's question and retrieve the top-k most semantically similar jobs. This handles Thai/English mixed queries well because the embedding model is multilingual.

**Q: How would you scale this to production at Soilfish?**
> Replace in-memory session store with Redis, ChromaDB local with a managed vector DB (Pinecone/Weaviate), add auth middleware (JWT), rate limiting, and deploy behind a load balancer. The FastAPI + Docker setup already supports horizontal scaling.

**Q: How do you monitor model quality over time?**
> Log every tool call and user feedback. Track: tool call frequency (which tools get called most), answer relevance scores, session length (longer = more engaged). Set up alerts if tool errors spike above a threshold.

---

## 🔧 Tech Stack

| Layer | Tech |
|---|---|
| LLM | Google Gemini 1.5 Flash (free) |
| Embeddings | Gemini text-embedding-004 |
| Vector DB | ChromaDB (persistent) |
| Agent | Gemini Function Calling |
| API | FastAPI + Uvicorn |
| UI | Streamlit |
| Config | Pydantic Settings |
| Logging | JSON structured logs |
| Tests | Pytest |
| Deploy | Docker + docker-compose |
