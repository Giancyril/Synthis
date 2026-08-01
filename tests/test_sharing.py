"""
Tests for Feature 1: Shareable Read-Only Report Links
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with output dir redirected to a temp directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    # Reset singleton so it re-initialises under tmp_path
    from src.services.database import reset_db
    reset_db()
    from src.server import app
    return TestClient(app)


def _make_report(tmp_path: Path, report_id: str, topic: str = "Test Topic") -> Path:
    """Write a minimal report JSON to tmp_path/output."""
    data = {
        "id": report_id,
        "topic": topic,
        "generated_at": "2026-01-01T00:00:00",
        "key_takeaways": [],
        "sections": [],
        "sources": [],
        "conflicting_information": [],
        "confidence_note": None,
        "filter_settings": None,
        "follow_ups": [],
        "share_token": None,
        "share_enabled": False,
        "share_created_at": None,
    }
    p = tmp_path / "output" / f"{report_id}.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    # Also create the .md counterpart so list_reports sees it
    (tmp_path / "output" / f"{report_id}.md").write_text("# Test", encoding="utf-8")
    return p


def test_share_report_generates_token(tmp_path, client):
    _make_report(tmp_path, "report_test")
    resp = client.post("/api/reports/report_test/share")
    assert resp.status_code == 200
    body = resp.json()
    assert body["share_enabled"] is True
    assert len(body["share_token"]) > 10
    assert "share_url" in body
    assert body["share_token"] in body["share_url"]


def test_share_twice_returns_same_token(tmp_path, client):
    _make_report(tmp_path, "report_test2")
    r1 = client.post("/api/reports/report_test2/share").json()
    r2 = client.post("/api/reports/report_test2/share").json()
    assert r1["share_token"] == r2["share_token"], "Token should be stable across re-shares"


def test_public_route_returns_report(tmp_path, client):
    _make_report(tmp_path, "report_pub", topic="Public Topic")
    share_resp = client.post("/api/reports/report_pub/share")
    token = share_resp.json()["share_token"]

    pub_resp = client.get(f"/api/public/reports/{token}")
    assert pub_resp.status_code == 200
    body = pub_resp.json()
    assert body["topic"] == "Public Topic"
    # Internal fields must NOT be present
    assert "id" not in body
    assert "share_token" not in body
    assert "share_enabled" not in body
    assert "filter_settings" not in body
    assert "follow_ups" not in body


def test_public_route_404_for_unknown_token(client):
    resp = client.get("/api/public/reports/nonexistenttoken123")
    assert resp.status_code == 404


def test_unshare_disables_link(tmp_path, client):
    _make_report(tmp_path, "report_revoke")
    token = client.post("/api/reports/report_revoke/share").json()["share_token"]

    # Confirm it's accessible
    assert client.get(f"/api/public/reports/{token}").status_code == 200

    # Revoke
    del_resp = client.delete("/api/reports/report_revoke/share")
    assert del_resp.status_code == 200
    assert del_resp.json()["share_enabled"] is False

    # Now 404
    assert client.get(f"/api/public/reports/{token}").status_code == 404


def test_share_report_not_found(client):
    resp = client.post("/api/reports/nonexistent_report/share")
    assert resp.status_code == 404
