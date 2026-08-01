"""
Tests for Feature 2: Annotations CRUD
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    # Reset singleton so it re-initialises under tmp_path
    from src.services.database import reset_db
    reset_db()
    from src.server import app
    return TestClient(app)


def test_create_annotation(client):
    resp = client.post(
        "/api/reports/report_abc/annotations",
        json={"target_type": "takeaway", "target_id": "0", "body": "Important note!"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("ann_")
    assert body["body"] == "Important note!"
    assert body["resolved"] is False
    assert body["report_id"] == "report_abc"


def test_list_annotations(client):
    client.post("/api/reports/rpt1/annotations", json={"target_type": "section", "target_id": "1", "body": "Note A"})
    client.post("/api/reports/rpt1/annotations", json={"target_type": "section", "target_id": "2", "body": "Note B"})
    resp = client.get("/api/reports/rpt1/annotations")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_patch_annotation_body(client):
    ann_id = client.post(
        "/api/reports/rpt2/annotations",
        json={"target_type": "source", "target_id": "S1", "body": "Old note"},
    ).json()["id"]

    patch_resp = client.patch(f"/api/annotations/{ann_id}", json={"body": "New note"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["body"] == "New note"


def test_patch_annotation_resolve(client):
    ann_id = client.post(
        "/api/reports/rpt3/annotations",
        json={"target_type": "takeaway", "target_id": "0", "body": "Resolve me"},
    ).json()["id"]

    patch_resp = client.patch(f"/api/annotations/{ann_id}", json={"resolved": True})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["resolved"] is True


def test_delete_annotation(client):
    ann_id = client.post(
        "/api/reports/rpt4/annotations",
        json={"target_type": "takeaway", "target_id": "1", "body": "Delete me"},
    ).json()["id"]

    del_resp = client.delete(f"/api/annotations/{ann_id}")
    assert del_resp.status_code == 204

    # Confirm it's gone from list
    remaining = client.get("/api/reports/rpt4/annotations").json()
    assert all(a["id"] != ann_id for a in remaining)


def test_invalid_target_type_rejected(client):
    resp = client.post(
        "/api/reports/rpt5/annotations",
        json={"target_type": "invalid", "target_id": "0", "body": "Bad"},
    )
    assert resp.status_code == 422


def test_empty_body_rejected(client):
    resp = client.post(
        "/api/reports/rpt6/annotations",
        json={"target_type": "section", "target_id": "0", "body": "   "},
    )
    assert resp.status_code == 422


def test_patch_nonexistent_annotation(client):
    resp = client.patch("/api/annotations/ann_doesnotexist", json={"body": "x"})
    assert resp.status_code == 404
