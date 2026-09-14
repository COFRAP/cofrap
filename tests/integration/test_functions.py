import pytest

pytestmark = pytest.mark.integration


def test_function_routes_are_independent_and_validate_direct_calls(client):
    password = client.function_clients["generate-password"]
    totp = client.function_clients["generate-2fa"]
    authentication = client.function_clients["authenticate"]
    assert password.post("/login", json={}).status_code == 404
    assert totp.post("/register", json={"username": "alice"}).status_code == 404
    assert authentication.post("/setup", json={}).status_code == 404
    response = authentication.post(
        "/login",
        json={
            "username": "alice",
            "password": "PRIVATE_PASSWORD",
            "code": "PRIVATE_CODE",
        },
    )
    assert response.status_code == 422
    assert "PRIVATE" not in response.text
    registration = password.post("/register", json={"username": "alice"})
    assert registration.status_code == 200
    assert registration.json()["delivery_qr"].startswith("data:image/png;base64,")
    assert registration.headers["Cache-Control"] == "no-store"
    token = registration.json()["delivery_token"]
    assert password.post("/redeem", json={"token": token}).status_code == 200
    assert password.post("/redeem", json={"token": token}).status_code == 401
