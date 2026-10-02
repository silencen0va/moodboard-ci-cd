import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200


def test_favorite_route(client):
    response = client.post(
        "/favorite",
        json={
            "id": "test-image",
            "url": "https://example.com/image.jpg",
            "link": "https://example.com",
            "user": "Test User",
            "likes": 10,
            "alt": "Test image"
        }
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "added"
    assert data["favorites_count"] == 1