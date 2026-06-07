# 🤖 Thai Job Market AI Agent

> AI-powered CV analyzer & job matcher for Thailand IT/Data market.
> Upload your CV (PDF) and AI will analyze your skills, find matching jobs from JobsDB, and tell you how well you fit each position.

---

## ✨ Features

- **CV Analysis** — Upload PDF (text or image-based), AI extracts and analyzes your profile
- **Job Matching** — Automatically matches your CV against real jobs from JobsDB Thailand
- **Match Scoring** — Each job gets a 0-100% match score with specific reasons why you fit (or don't)
- **Skill Gap Detection** — Shows skills you have vs. skills the market demands
- **Real Job Links** — Click through to apply on JobsDB directly

---

## 🏗️ Architecture

```
User (Streamlit UI)
        │
        ▼
  FastAPI Backend
   ├── POST /cv/analyze     → CV Analysis + Job Matching
   │    ├── PyMuPDF          (text extraction)
   │    ├── Gemini Vision    (image-based PDF fallback)
   │    ├── ChromaDB RAG     (semantic job search)
   │    └── Gemini LLM       (analysis + match scoring)
   │
   ├── POST /jobs/search     → Semantic Job Search
   ├── POST /jobs/salary     → Salary Analysis
   ├── POST /jobs/skill-gap  → Skill Gap Check
   └── POST /chat            → Multi-turn Agent Chat
        │
        ▼
  ChromaDB (vector store with 90 real jobs from JobsDB)
  Gemini Embedding API (gemini-embedding-001)
```

---

## 🔧 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **LLM** | Google Gemini 2.0 Flash | CV analysis, job matching, chat agent |
| **Vision AI** | Gemini 2.0 Flash (multimodal) | Read image-based/scanned PDF CVs |
| **Embeddings** | Gemini Embedding 001 | Semantic search vectors |
| **Vector DB** | ChromaDB (persistent) | Job listings storage & similarity search |
| **Agent** | Gemini Function Calling | Auto tool selection for chat |
| **Backend** | FastAPI + Uvicorn | REST API |
| **Frontend** | Streamlit | CV upload UI + results display |
| **PDF Parser** | PyMuPDF (fitz) | Extract text & render pages from PDF |
| **Scraper** | Requests + BeautifulSoup | Scrape jobs from JobsDB Thailand |
| **Config** | Pydantic Settings | Environment-based configuration |
| **Logging** | JSON structured logs | Production-ready logging |
| **Testing** | Pytest | Unit tests |
| **Deploy** | Docker + docker-compose | Containerized deployment |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/Naminshxn31/thai-job-agent.git
cd thai-job-agent

cp .env.example .env
# Edit .env — add your GEMINI_API_KEY
# Get free key at: https://aistudio.google.com/apikey
```

### 2. Run with Docker (recommended)

```bash
docker-compose up --build
```

### 3. Load job data

```bash
# Scrape real jobs from JobsDB Thailand
docker-compose exec api python scripts/load_jobs.py --source scrape --pages 3

# Or generate synthetic data for demo
docker-compose exec api python scripts/load_jobs.py --source synthetic
```

### 4. Open the app

- **UI**: http://localhost:8501
- **API docs**: http://localhost:8000/docs

---

## 💻 Run without Docker

```bash
pip install -r requirements.txt

# Load data
python scripts/load_jobs.py --source scrape --pages 3

# Terminal 1 — API
uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — UI
streamlit run app/ui/streamlit_app.py
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/cv/analyze` | Upload CV (PDF) → AI analysis + job matching |
| `POST` | `/jobs/search` | Semantic job search |
| `POST` | `/jobs/salary` | Salary analysis by role |
| `POST` | `/jobs/skill-gap` | Skill gap analysis |
| `POST` | `/chat` | Multi-turn agent chat |
| `GET` | `/health` | Health check |

### CV Analysis example

```bash
curl -X POST http://localhost:8000/cv/analyze \
  -F "file=@my_cv.pdf"
```

Response includes:
- `profile_summary` — AI summary of your profile
- `skills_found` — Skills detected in your CV
- `skills_missing` — Skills the market wants but you lack
- `recommendations` — Actionable advice
- `matched_jobs` — Jobs ranked by match score with reasons

---

## 📁 Project Structure

```
thai-job-agent/
├── app/
│   ├── config.py              # Pydantic settings (env-based)
│   ├── logger.py              # JSON structured logging
│   ├── agent/
│   │   └── core.py            # Gemini Function Calling agent
│   ├── api/
│   │   └── main.py            # FastAPI + /cv/analyze endpoint
│   ├── rag/
│   │   └── retriever.py       # ChromaDB semantic search
│   ├── tools/
│   │   └── job_tools.py       # Agent tools + dispatcher
│   └── ui/
│       └── streamlit_app.py   # Streamlit CV-first UI
├── scripts/
│   └── load_jobs.py           # JobsDB scraper + data ingestion
├── tests/
│   └── test_tools.py          # Unit tests
├── data/chroma/               # Persisted vector store (gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 📸 Screenshots

### CV Upload & Analysis
Upload your CV → AI reads it (even scanned PDFs) → shows your profile summary, skills, and recommendations.

### Job Matching
Each job gets a match score with specific reasons:
- ✅ Why you're a good fit
- ⚠️ What skills you're missing
- 🔗 Direct link to apply on JobsDB

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model for chat/analysis |
| `GEMINI_EMBEDDING_MODEL` | No | `gemini-embedding-001` | Embedding model |
| `CHROMA_PERSIST_DIR` | No | `./data/chroma` | ChromaDB storage path |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## License

MIT
