"""
Feature: kirin-runtime, Integration Tests
FastAPI TestClient tests for /health, /capabilities, and endpoint validation.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


def make_test_client():
    with patch("core.server.os.environ", {
        "REDIS_URL": "redis://localhost:6379",
        "POSTGRES_URL": "postgresql://localhost:5432",
        "QDRANT_URL": "http://localhost:6333",
    }):
        from core.server import app
        return TestClient(app)


def test_health_returns_ok():
    client = make_test_client()
    with client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "2.0.0"
    assert body["phase"] == "2"


def test_capabilities_list():
    client = make_test_client()
    with client:
        resp = client.get("/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert "capabilities" in body
    names = [c["name"] for c in body["capabilities"]]
    assert "score_lead" in names
    assert "enrich_lead" in names


def test_capabilities_get_existing():
    client = make_test_client()
    with client:
        resp = client.get("/capabilities/score_lead")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "score_lead"
    assert "cost_profile" in body
    assert "latency_profile" in body
    assert "provider_requirements" in body


def test_capabilities_get_nonexistent():
    client = make_test_client()
    with client:
        resp = client.get("/capabilities/nonexistent_capability")
    assert resp.status_code == 404
    body = resp.json()
    assert "não encontrada" in body["detail"]


def test_invoke_rejects_empty_goal():
    client = make_test_client()
    with client:
        resp = client.post("/invoke", json={
            "goal": "",
            "context": {},
            "memory_id": "test-123",
        })
    assert resp.status_code == 422


def test_invoke_rejects_whitespace_goal():
    client = make_test_client()
    with client:
        resp = client.post("/invoke", json={
            "goal": "   ",
            "context": {},
            "memory_id": "test-123",
        })
    assert resp.status_code == 422


def test_invoke_rejects_missing_goal():
    client = make_test_client()
    with client:
        resp = client.post("/invoke", json={
            "context": {},
            "memory_id": "test-123",
        })
    assert resp.status_code == 422


def test_state_endpoint_not_found():
    client = make_test_client()
    with client:
        resp = client.get("/agents/nonexistent/state")
    assert resp.status_code == 404


def test_heartbeat_returns_ok():
    client = make_test_client()
    with client:
        resp = client.post("/agents/test-mem/heartbeat")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


def test_invoke_rejects_invalid_json():
    client = make_test_client()
    with client:
        resp = client.post("/invoke", content="not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_capabilities_structure():
    client = make_test_client()
    with client:
        resp = client.get("/capabilities/score_lead")
    cap = resp.json()
    assert "name" in cap
    assert "description" in cap
    assert "input_schema" in cap
    assert "output_schema" in cap
    assert "cost_profile" in cap
    assert "latency_profile" in cap
    assert "deterministic" in cap
    assert "tags" in cap
    assert cap["cost_profile"]["currency"] == "USD"
    assert isinstance(cap["latency_profile"]["p50_ms"], int)
    assert isinstance(cap["latency_profile"]["p95_ms"], int)
    assert isinstance(cap["latency_profile"]["p99_ms"], int)
