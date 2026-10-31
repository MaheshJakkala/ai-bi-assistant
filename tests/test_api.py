import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_sales.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", db_path)
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dataset"]["transactions_loaded"] == 49
    assert body["dataset"]["rejected_rows"] == 2


def test_examples_endpoint(client):
    response = client.get("/api/examples")
    assert response.status_code == 200
    assert len(response.json()["examples"]) >= 5


@pytest.mark.parametrize(
    "question,expected_intent",
    [
        ("What is the total revenue?", "total_revenue"),
        ("Which product generated the highest revenue?", "top_product"),
        ("What is the monthly revenue trend?", "monthly_trend"),
        ("Which region generated the highest sales?", "top_region"),
        ("How did revenue change between January and February?", "compare_months"),
    ],
)
def test_supported_questions(client, question, expected_intent):
    response = client.post("/api/ask", json={"question": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == expected_intent
    assert body["answer"]
    assert body["data"]
    assert body["sql"].lower().startswith("select")


def test_total_revenue_number_is_correct(client):
    response = client.post("/api/ask", json={"question": "what is the total revenue"})
    body = response.json()
    assert body["data"][0]["value"] == pytest.approx(1439200.0)


def test_comparison_requires_two_months(client):
    response = client.post(
        "/api/ask", json={"question": "compare revenue between months"}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_question"


def test_unsupported_question_returns_422(client):
    response = client.post(
        "/api/ask", json={"question": "Who is the CEO of the company?"}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_question"


def test_empty_question_rejected_by_validation(client):
    response = client.post("/api/ask", json={"question": ""})
    assert response.status_code == 422


def test_whitespace_question_returns_friendly_error(client):
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 422
    assert "question" in response.json()["detail"].lower()


def test_sql_never_destructive(client):
    response = client.post("/api/ask", json={"question": "What is the total revenue?"})
    sql = response.json()["sql"].lower()
    for keyword in ("delete", "drop", "update", "insert"):
        assert keyword not in sql


def test_index_page_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Mini AI BI Assistant" in response.text
