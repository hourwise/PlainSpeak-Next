"""The local web interface presents through the governed pipeline.

Its "Simplified Text" was once produced by the inherited substitution engine,
with no integrity firewall: "leverages" became "borrowed money" and "shall"
became "must". It now comes from `present`, the same operation as
`plainspeak present`, so it can only contain SAFE changes.
"""
from __future__ import annotations

import pytest

pytest.importorskip("flask")

from plainspeak.adapters.web import WEB_PROFILE, create_app  # noqa: E402
from plainspeak.pipeline import present_text  # noqa: E402

TEXT = "The system leverages a cache. Staff shall not utilize it before 3 June 2027."


@pytest.fixture
def client():
    return create_app().test_client()


def _analyze(client, **body):
    response = client.post("/api/analyze", json={"text": TEXT, **body})
    return response.status_code, response.get_json()


def test_simplified_text_is_the_governed_presentation(client):
    status, data = _analyze(client)
    assert status == 200
    expected = present_text(TEXT, WEB_PROFILE)
    assert data["simplified_text"] == expected.marked_text()
    assert data["presentation"]["output_sha256"] == expected.preview.output_hash


def test_the_inherited_engine_output_cannot_appear(client):
    _, data = _analyze(client)
    assert "borrowed money" not in data["simplified_text"]
    assert "shall not" in data["simplified_text"]
    assert "3 June 2027" in data["simplified_text"]


def test_the_profile_is_reported_and_can_be_chosen(client):
    _, default = _analyze(client)
    _, technical = _analyze(client, profile="technical")
    assert default["presentation"]["profile"] == WEB_PROFILE == "natural"
    assert technical["presentation"]["profile"] == "technical"


def test_an_unknown_profile_is_refused(client):
    status, data = _analyze(client, profile="casual")
    assert status == 400
    assert data["code"] == "unknown_profile"


def test_the_page_describes_the_governed_presentation(client):
    page = client.get("/").get_data(as_text=True)
    assert "Governed presentation." in page
    assert "Legacy, unguarded" not in page
