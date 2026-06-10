"""Integration tests for the self-service preview + publish flow.

The researcher review step was removed: the practitioner previews the whole
page and publishes it themselves, and publishing is reversible (they can go
back to the interview and keep editing).
"""
import os
import re

import pytest
from starlette.testclient import TestClient

from pagecraft.main import create_app


@pytest.fixture
def app(tmp_path):
    os.environ["PAGECRAFT_DB_PATH"] = str(tmp_path / "test.db")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _new_page(client) -> tuple[int, str]:
    """Create a page and return (page_id, uri_token)."""
    resp = client.get("/", follow_redirects=False)
    page_id = int(resp.headers["location"].split("/")[-1])
    interview = client.get(f"/interview/{page_id}")
    token = re.search(r'/preview/([A-Za-z0-9_-]+)', interview.text).group(1)
    return page_id, token


def test_case_is_404_before_publish(client):
    page_id, _ = _new_page(client)
    assert client.get(f"/case/{page_id}").status_code == 404


def test_preview_shows_publish_button_before_publishing(client):
    _, token = _new_page(client)
    resp = client.get(f"/preview/{token}")
    assert resp.status_code == 200
    assert f"/preview/{token}/publish" in resp.text
    assert "Publicera" in resp.text


def test_publish_makes_case_reachable(client):
    page_id, token = _new_page(client)

    publish = client.post(f"/preview/{token}/publish", follow_redirects=False)
    assert publish.status_code == 303
    assert publish.headers["location"] == f"/preview/{token}"

    # Preview now reflects the published state and links to the public page.
    preview = client.get(f"/preview/{token}")
    assert "Publicerad" in preview.text
    assert f"/case/{page_id}" in preview.text

    # The public case view is reachable.
    assert client.get(f"/case/{page_id}").status_code == 200


def test_publish_is_reversible_interview_still_open(client):
    """After publishing, the interview page still loads so editing can continue."""
    page_id, token = _new_page(client)
    client.post(f"/preview/{token}/publish", follow_redirects=False)
    assert client.get(f"/interview/{page_id}").status_code == 200


def test_publish_unknown_token_404(client):
    assert client.post("/preview/nope/publish", follow_redirects=False).status_code == 404
