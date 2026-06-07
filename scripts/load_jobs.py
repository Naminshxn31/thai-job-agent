"""
scripts/load_jobs.py
Scrape job listings OR load from CSV → ingest into ChromaDB

Usage:
  python scripts/load_jobs.py --source csv --file data/jobs.csv
  python scripts/load_jobs.py --source scrape --pages 5
"""
import argparse
import time
import uuid
import random
import json
from pathlib import Path
from typing import Generator

import pandas as pd
import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings as ChromaSettings
from google import genai

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.logger import setup_logger

log = setup_logger("load_jobs")
settings = get_settings()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── SYNTHETIC FALLBACK DATA ────────────────────────────────
def generate_synthetic_jobs(n: int = 200) -> list[dict]:
    """Fallback: generate realistic synthetic job data if scraping fails"""
    import random, datetime

    ROLES = [
        "ML Engineer", "Data Scientist", "AI Engineer",
        "Data Engineer", "NLP Engineer", "LLM Engineer",
        "MLOps Engineer", "Computer Vision Engineer",
    ]
    COMPANIES = [
        "Bitkub", "SCB Tech", "Agoda", "Lazada Thailand",
        "True Digital", "PTT Digital", "Grab Thailand",
        "LINE Thailand", "Shopee Thailand", "Kasikorn Bank",
        "CP Group", "AIS", "DTAC", "TrueMove H",
    ]
    SKILLS_POOL = [
        ["Python", "TensorFlow", "Keras", "Docker"],
        ["Python", "PyTorch", "MLflow", "Kubernetes"],
        ["Python", "LangChain", "OpenAI API", "FastAPI"],
        ["Python", "scikit-learn", "SQL", "Airflow"],
        ["Python", "HuggingFace", "RAG", "Vector DB"],
        ["Python", "Spark", "Kafka", "dbt"],
        ["Python", "YOLO", "OpenCV", "TensorRT"],
    ]
    LOCATIONS = ["Bangkok", "Hybrid - Bangkok", "Remote", "Chiang Mai", "Phuket"]

    jobs = []
    for i in range(n):
        salary_min = random.choice([40000, 50000, 60000, 70000, 80000, 100000])
        salary_max = salary_min + random.choice([10000, 20000, 30000, 40000])
        skills = random.choice(SKILLS_POOL) + random.sample(
            ["Git", "CI/CD", "AWS", "GCP", "Azure", "PostgreSQL", "Redis"], 2
        )
        posted_days_ago = random.randint(0, 30)
        posted_date = (
            datetime.date.today() - datetime.timedelta(days=posted_days_ago)
        ).isoformat()

        jobs.append({
            "id": str(uuid.uuid4()),
            "title": random.choice(ROLES),
            "company": random.choice(COMPANIES),
            "location": random.choice(LOCATIONS),
            "salary_min": salary_min,
            "salary_max": salary_max,
            "skills": skills,
            "description": (
                f"We are looking for a {random.choice(ROLES)} to join our team at "
                f"{random.choice(COMPANIES)}. You will build and deploy ML models, "
                f"work with {', '.join(skills[:3])}, and collaborate with cross-functional teams. "
                f"Salary: {salary_min:,}–{salary_max:,} THB/month."
            ),
            "experience_years": random.choice([1, 2, 3, 5]),
            "posted_date": posted_date,
            "source": "synthetic",
        })
    return jobs

# ─── SCRAPER ────────────────────────────────────────────────
def scrape_jobsdb(pages: int = 3) -> list[dict]:
    """Scrape JobsDB Thailand — falls back to synthetic on error"""
    jobs = []
    base_url = "https://th.jobsdb.com/th/search-jobs/data-science-machine-learning"

    for page in range(1, pages + 1):
        try:
            url = f"{base_url}/{page}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Try multiple selectors for robustness
            cards = soup.select("[data-automation='job-card-title']")
            if not cards:
                cards = soup.select("a[data-automation='jobTitle']")
            if not cards:
                # Fallback: find all article elements with job links
                cards = soup.select("article h3 a, article h2 a")
            if not cards:
                log.warning(f"No cards found on page {page} — site structure may have changed")
                break

            for card in cards:
                title = card.get_text(strip=True)

                # Extract job URL
                job_url = ""
                link_el = card if card.name == "a" else card.find("a")
                if link_el and link_el.get("href"):
                    href = link_el["href"]
                    if href.startswith("/"):
                        job_url = f"https://th.jobsdb.com{href}"
                    elif href.startswith("http"):
                        job_url = href

                parent = card.find_parent("article") or card.find_parent("div", class_=True)
                company = ""
                salary = ""
                location = ""
                if parent:
                    co_el = (
                        parent.select_one("[data-automation='job-card-company']")
                        or parent.select_one("[data-automation='jobCompany']")
                    )
                    sal_el = (
                        parent.select_one("[data-automation='job-card-salary']")
                        or parent.select_one("[data-automation='jobSalary']")
                    )
                    loc_el = (
                        parent.select_one("[data-automation='job-card-location']")
                        or parent.select_one("[data-automation='jobLocation']")
                    )
                    company = co_el.get_text(strip=True) if co_el else ""
                    salary  = sal_el.get_text(strip=True) if sal_el else ""
                    location = loc_el.get_text(strip=True) if loc_el else ""

                jobs.append({
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "company": company,
                    "location": location or "Thailand",
                    "salary_raw": salary,
                    "url": job_url,
                    "source": "jobsdb",
                    "description": f"{title} at {company}. Location: {location}. Salary: {salary}",
                })

            log.info(f"Scraped page {page}: {len(cards)} jobs")
            time.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            log.warning(f"Scraping failed on page {page}: {e}. Using synthetic data.")
            break

    if not jobs:
        log.info("No scraped jobs — generating synthetic dataset")
        jobs = generate_synthetic_jobs(200)

    return jobs

# ─── LOAD FROM CSV ───────────────────────────────────────────
def load_from_csv(path: str) -> list[dict]:
    df = pd.read_csv(path)
    df = df.fillna("")
    required = {"title", "company", "description"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")
    jobs = df.to_dict(orient="records")
    for j in jobs:
        if "id" not in j or not j["id"]:
            j["id"] = str(uuid.uuid4())
    log.info(f"Loaded {len(jobs)} jobs from {path}")
    return jobs

# ─── EMBEDDING ───────────────────────────────────────────────
def embed_texts(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    client = genai.Client(api_key=settings.gemini_api_key)
    all_embeddings = []
    total_batches = (len(texts) - 1) // batch_size + 1
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(5):
            try:
                result = client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=batch,
                )
                all_embeddings.extend([e.values for e in result.embeddings])
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    wait = (attempt + 1) * 15
                    log.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        log.info(f"Embedded batch {i//batch_size + 1}/{total_batches}")
        time.sleep(2.0)
    return all_embeddings

# ─── INGEST TO CHROMA ────────────────────────────────────────
def ingest(jobs: list[dict]):
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    col = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )

    texts = [j.get("description", j.get("title", "")) for j in jobs]
    ids   = [j["id"] for j in jobs]
    metas = [
        {
            "title":    str(j.get("title", "")),
            "company":  str(j.get("company", "")),
            "location": str(j.get("location", "")),
            "salary_min": int(j.get("salary_min", 0)),
            "salary_max": int(j.get("salary_max", 0)),
            "skills":   json.dumps(j.get("skills", []), ensure_ascii=False),
            "url":      str(j.get("url", "")),
            "source":   str(j.get("source", "unknown")),
        }
        for j in jobs
    ]

    log.info(f"Embedding {len(jobs)} jobs...")
    embeddings = embed_texts(texts)

    col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metas)
    log.info(f"✅ Ingested {len(jobs)} jobs into ChromaDB collection '{settings.chroma_collection}'")

# ─── MAIN ────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "scrape", "synthetic"], default="synthetic")
    parser.add_argument("--file",   default="data/jobs.csv", help="CSV path (if --source csv)")
    parser.add_argument("--pages",  type=int, default=3, help="Pages to scrape")
    args = parser.parse_args()

    if args.source == "csv":
        jobs = load_from_csv(args.file)
    elif args.source == "scrape":
        jobs = scrape_jobsdb(pages=args.pages)
    else:
        log.info("Generating synthetic dataset...")
        jobs = generate_synthetic_jobs(200)

    ingest(jobs)
