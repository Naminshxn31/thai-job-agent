"""
app/tools/job_tools.py
3 tools ที่ LLM Agent เรียกใช้:
  1. job_search        — ค้นหางานด้วย semantic search
  2. salary_analysis   — วิเคราะห์เงินเดือนตาม role/skill
  3. skill_gap_check   — เปรียบเทียบ skills ที่มีกับที่ตลาดต้องการ
"""
import json
from typing import Any

from app.rag.retriever import JobRetriever
from app.logger import setup_logger

log = setup_logger("tools")

# ─── TOOL SCHEMAS (Gemini function declarations) ─────────────
TOOL_DECLARATIONS = [
    {
        "name": "job_search",
        "description": (
            "Search for job listings in Thailand's IT/Data market. "
            "Use this when the user asks about available jobs, companies hiring, "
            "or wants to find positions matching specific criteria."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Job search query e.g. 'ML Engineer Bangkok Python'",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 10)",
                },
                "salary_min": {
                    "type": "integer",
                    "description": "Minimum salary filter in THB (optional)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "salary_analysis",
        "description": (
            "Analyze salary ranges for specific roles or skills in Thailand. "
            "Use this when the user asks about salary expectations, pay ranges, "
            "or how much a specific role pays."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "Job role to analyze e.g. 'Data Scientist', 'ML Engineer'",
                },
                "skill": {
                    "type": "string",
                    "description": "Specific skill to filter by e.g. 'PyTorch', 'LangChain' (optional)",
                },
            },
            "required": ["role"],
        },
    },
    {
        "name": "skill_gap_check",
        "description": (
            "Compare a candidate's skills against what the market demands for a role. "
            "Use this when the user wants to know what skills they're missing, "
            "or what to learn to be more competitive."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_role": {
                    "type": "string",
                    "description": "The role the candidate is targeting",
                },
                "current_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of skills the candidate currently has",
                },
            },
            "required": ["target_role", "current_skills"],
        },
    },
]


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────
def job_search(
    query: str,
    n_results: int = 5,
    salary_min: int | None = None,
) -> dict[str, Any]:
    retriever = JobRetriever()
    jobs = retriever.search(query=query, n_results=n_results, salary_min=salary_min)

    if not jobs:
        return {"jobs": [], "summary": "No matching jobs found."}

    summary_lines = []
    for j in jobs:
        sal = (
            f"{j['salary_min']:,}–{j['salary_max']:,} THB"
            if j["salary_min"]
            else "Salary not specified"
        )
        summary_lines.append(
            f"- {j['title']} @ {j['company']} | {j['location']} | {sal} | "
            f"Skills: {', '.join(j['skills'][:4])} | Relevance: {j['relevance']}"
        )

    log.info(f"job_search: query='{query}' → {len(jobs)} results")
    return {
        "jobs": jobs,
        "total_found": len(jobs),
        "summary": "\n".join(summary_lines),
    }


def salary_analysis(role: str, skill: str | None = None) -> dict[str, Any]:
    retriever = JobRetriever()
    query = f"{role} salary Thailand" + (f" {skill}" if skill else "")
    jobs = retriever.search(query=query, n_results=20)

    if not jobs:
        return {"error": f"No data found for role: {role}"}

    salaries = [
        j["salary_min"]
        for j in jobs
        if j["salary_min"] > 0
    ] + [
        j["salary_max"]
        for j in jobs
        if j["salary_max"] > 0
    ]

    if not salaries:
        return {"role": role, "note": "Salary data not available in current dataset"}

    result = {
        "role": role,
        "skill_filter": skill,
        "sample_size": len(jobs),
        "salary_min_thb":  min(salaries),
        "salary_max_thb":  max(salaries),
        "salary_avg_thb":  int(sum(salaries) / len(salaries)),
        "salary_median_thb": int(sorted(salaries)[len(salaries) // 2]),
        "top_companies": list({j["company"] for j in jobs[:5]}),
    }
    log.info(f"salary_analysis: role='{role}' → avg={result['salary_avg_thb']:,}")
    return result


def skill_gap_check(
    target_role: str,
    current_skills: list[str],
) -> dict[str, Any]:
    retriever = JobRetriever()
    jobs = retriever.search(query=f"{target_role} required skills Thailand", n_results=15)

    if not jobs:
        return {"error": f"No data found for role: {target_role}"}

    market_skills: dict[str, int] = {}
    for j in jobs:
        for s in j.get("skills", []):
            market_skills[s.lower()] = market_skills.get(s.lower(), 0) + 1

    top_market = sorted(market_skills.items(), key=lambda x: -x[1])[:15]
    top_market_names = [s for s, _ in top_market]

    current_lower = [s.lower() for s in current_skills]
    missing   = [s for s in top_market_names if s not in current_lower]
    matched   = [s for s in top_market_names if s in current_lower]

    match_pct = round(len(matched) / len(top_market_names) * 100) if top_market_names else 0

    result = {
        "target_role": target_role,
        "match_percentage": match_pct,
        "matched_skills": matched,
        "missing_skills": missing[:8],
        "top_market_skills": top_market_names,
        "recommendation": (
            f"You match {match_pct}% of skills for {target_role}. "
            f"Focus on learning: {', '.join(missing[:3])}."
        ),
    }
    log.info(f"skill_gap: role='{target_role}' match={match_pct}%")
    return result


# ─── DISPATCHER ───────────────────────────────────────────────
TOOL_FN_MAP = {
    "job_search":      job_search,
    "salary_analysis": salary_analysis,
    "skill_gap_check": skill_gap_check,
}


def dispatch_tool(name: str, args: dict) -> str:
    fn = TOOL_FN_MAP.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**args)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        log.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
