from fastapi.testclient import TestClient

from optometry.main import app

# make http requests to FastAPI without starting a real web server
client = TestClient(app)


# test api is running
def test_health_endpoint_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


# predictable response
def test_health_endpoint_returns_expected_json():
    response = client.get("/health")
    assert response.json() == {
        "status": "ok",
        "service": "optometry-booking-api",
    }
