"""Integration tests for the researcher review UI."""
import json
import os
import re

import pytest
from starlette.testclient import TestClient

from pagecraft.main import create_app

DEMO_MSG_COUNT = 6


@pytest.fixture
def app(tmp_path):
    os.environ["PAGECRAFT_DB_PATH"] = str(tmp_path / "test.db")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _new_page(client) -> int:
    r = client.get("/", follow_redirects=False)
    return int(r.headers["location"].split("/")[-1])


def _fill_and_end(client, page_id, text="Hej"):
    """Demo-fill one component (situation) and end the interview."""
    with client.websocket_connect(f"/ws/{page_id}") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": text}))
        for _ in range(DEMO_MSG_COUNT):
            ws.receive_text()
        ws.send_text(json.dumps({"type": "end_interview"}))
        for _ in range(2):
            ws.receive_text()


def _get_review(client, page_id, expect_annotations=False, tries=10):
    """GET the review page, retrying to let the background canned-annotation
    task finish when annotations are expected (each request pumps the loop)."""
    r = client.get(f"/review/{page_id}")
    for _ in range(tries):
        if not expect_annotations or "ann-" in r.text:
            return r
        r = client.get(f"/review/{page_id}")
    return r


def test_review_index_lists_awaiting(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = client.get("/review")
    assert r.status_code == 200
    assert f"/review/{pid}" in r.text


def test_review_404_for_in_interview(client):
    pid = _new_page(client)  # never ended → still in_interview
    assert client.get(f"/review/{pid}").status_code == 404


def test_review_page_renders(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = client.get(f"/review/{pid}")
    assert r.status_code == 200
    assert "Annoteringar" in r.text
    assert "review-comp-" in r.text


def test_component_review_toggle(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = client.get(f"/review/{pid}")
    cid = int(re.search(r"review-comp-(\d+)", r.text).group(1))
    r2 = client.post(f"/review/{pid}/component/{cid}/review", data={"reviewed": "true"})
    assert r2.status_code == 200
    assert "is-reviewed" in r2.text


def test_component_edit(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = client.get(f"/review/{pid}")
    cid = int(re.search(r"review-comp-(\d+)", r.text).group(1))
    rf = client.get(f"/review/{pid}/component/{cid}/edit-form")
    assert rf.status_code == 200
    assert "current_situation" in rf.text
    redit = client.post(
        f"/review/{pid}/component/{cid}/edit",
        data={"current_situation": "Nytt nuläge", "challenge": "X", "solution": "Y"},
    )
    assert redit.status_code == 200
    assert "Nytt nuläge" in redit.text


def test_annotation_decision(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = _get_review(client, pid, expect_annotations=True)
    aid = int(re.search(r"ann-(\d+)", r.text).group(1))
    rd = client.post(
        f"/review/{pid}/annotation/{aid}",
        data={"decision": "acknowledged", "curator_note": "ok"},
    )
    assert rd.status_code == 200
    assert "Bekräftad" in rd.text


def test_publish_blocked_until_ready(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    _get_review(client, pid, expect_annotations=True)
    rp = client.post(f"/review/{pid}/publish")
    assert rp.status_code == 200
    assert "måste vara granskade" in rp.text


def test_publish_success(client):
    pid = _new_page(client)
    _fill_and_end(client, pid)
    r = _get_review(client, pid, expect_annotations=True)
    cid = int(re.search(r"review-comp-(\d+)", r.text).group(1))
    aid = int(re.search(r"ann-(\d+)", r.text).group(1))
    client.post(f"/review/{pid}/component/{cid}/review", data={"reviewed": "true"})
    client.post(f"/review/{pid}/annotation/{aid}", data={"decision": "acknowledged"})
    rp = client.post(f"/review/{pid}/publish")
    assert "Publicerad" in rp.text
