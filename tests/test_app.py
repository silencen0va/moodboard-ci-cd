import pytest
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
            "image": {
                "id": "test-image",
                "url": "https://example.com/image.jpg"
            }
        }
    )

    assert response.status_code == 200