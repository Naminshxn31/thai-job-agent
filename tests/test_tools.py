"""
tests/test_tools.py
Unit tests — mock ChromaDB so no real API calls needed
"""
import json
import pytest
from unittest.mock import MagicMock, patch


MOCK_JOBS = [
    {
        "description": "ML Engineer at Bitkub, Python PyTorch MLflow",
        "title": "ML Engineer",
        "company": "Bitkub",
        "location": "Bangkok",
        "salary_min": 80000,
        "salary_max": 120000,
        "skills": ["Python", "PyTorch", "MLflow", "Docker"],
        "relevance": 0.95,
    },
    {
        "description": "Data Scientist at Agoda, Python scikit-learn SQL",
        "title": "Data Scientist",
        "company": "Agoda",
        "location": "Bangkok",
        "salary_min": 60000,
        "salary_max": 90000,
        "skills": ["Python", "scikit-learn", "SQL", "Airflow"],
        "relevance": 0.87,
    },
]


@pytest.fixture
def mock_retriever():
    with patch("app.tools.job_tools.JobRetriever") as MockRetriever:
        instance = MagicMock()
        instance.search.return_value = MOCK_JOBS
        MockRetriever.return_value = instance
        yield instance


def test_job_search_returns_results(mock_retriever):
    from app.tools.job_tools import job_search
    result = job_search(query="ML Engineer Bangkok", n_results=5)
    assert result["total_found"] == 2
    assert len(result["jobs"]) == 2
    assert "summary" in result


def test_job_search_no_results(mock_retriever):
    from app.tools.job_tools import job_search
    mock_retriever.search.return_value = []
    result = job_search(query="astronaut Bangkok")
    assert result["jobs"] == []
    assert "No matching" in result["summary"]


def test_salary_analysis(mock_retriever):
    from app.tools.job_tools import salary_analysis
    result = salary_analysis(role="ML Engineer")
    assert result["salary_avg_thb"] > 0
    assert result["salary_min_thb"] <= result["salary_max_thb"]
    assert "Bitkub" in result["top_companies"] or "Agoda" in result["top_companies"]


def test_skill_gap_check(mock_retriever):
    from app.tools.job_tools import skill_gap_check
    result = skill_gap_check(
        target_role="ML Engineer",
        current_skills=["Python", "scikit-learn"],
    )
    assert "match_percentage" in result
    assert isinstance(result["missing_skills"], list)
    assert 0 <= result["match_percentage"] <= 100


def test_dispatch_tool_unknown():
    from app.tools.job_tools import dispatch_tool
    result = json.loads(dispatch_tool("nonexistent_tool", {}))
    assert "error" in result


def test_dispatch_tool_valid(mock_retriever):
    from app.tools.job_tools import dispatch_tool
    result = json.loads(dispatch_tool("job_search", {"query": "ML Engineer"}))
    assert "jobs" in result
