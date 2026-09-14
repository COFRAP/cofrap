import httpx
import pytest
from fastapi.testclient import TestClient

from cofrap.domain.errors import BackendUnavailable, InvalidCredentials
from cofrap.frontend.main import create_app
from cofrap.frontend.openfaas_client import OpenFaaSClient
from cofrap.frontend.settings import FrontendSettings


def test_timeout_does_not_retry_one_use_operation():
    calls = []

    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(fail)) as http:
        with pytest.raises(BackendUnavailable):
            OpenFaaSClient(http).call("generate-password", "redeem", {"token": "x" * 43})
    assert len(calls) == 1


def test_domain_error_survives_http_boundary():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(401, json={"error": {"code": "invalid_credentials"}})
    )
    with httpx.Client(base_url="http://gateway", transport=transport) as http:
        with pytest.raises(InvalidCredentials):
            OpenFaaSClient(http).call("authenticate", "login", {})


def test_frontend_starts_without_database_credentials_and_handles_gateway_failure():
    settings = FrontendSettings(_env_file=None)
    transport = httpx.MockTransport(lambda _: httpx.Response(502, text="upstream error"))
    with TestClient(create_app(settings, transport=transport)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        response = client.post("/api/users", json={"username": "alice"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "backend_unavailable"
