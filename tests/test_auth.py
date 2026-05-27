from __future__ import annotations

from fastapi.testclient import TestClient

from distributor.main import app


def _payload() -> dict:
    return {"project_slug": "psf/requests", "prompt": "hello"}


def test_no_token_configured_allows_all(monkeypatch):
    monkeypatch.delenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", raising=False)
    client = TestClient(app)
    resp = client.post("/tasks", json=_payload())
    assert resp.status_code == 200


def test_missing_authorization_header_when_token_set(monkeypatch):
    monkeypatch.setenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "secret")
    client = TestClient(app)
    resp = client.post("/tasks", json=_payload())
    assert resp.status_code == 401


def test_wrong_token(monkeypatch):
    monkeypatch.setenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "secret")
    client = TestClient(app)
    resp = client.post(
        "/tasks",
        json=_payload(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 403


def test_correct_token(monkeypatch):
    monkeypatch.setenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "secret")
    client = TestClient(app)
    resp = client.post(
        "/tasks",
        json=_payload(),
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 200


def test_healthz_unauthenticated(monkeypatch):
    monkeypatch.setenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "secret")
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_list_tasks_unauthenticated(monkeypatch):
    monkeypatch.setenv("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "secret")
    client = TestClient(app)
    resp = client.get("/tasks")
    assert resp.status_code == 200
