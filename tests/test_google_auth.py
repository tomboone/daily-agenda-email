import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.google_auth import create_auth_router
from src.secrets import SecretsClient


@pytest.fixture
def mock_secrets() -> MagicMock:
    secrets = MagicMock(spec=SecretsClient)
    secrets.get_secret.return_value = json.dumps(
        {"client_id": "test-client-id", "client_secret": "test-client-secret"}
    )
    return secrets


@pytest.fixture
def app(mock_secrets: MagicMock) -> FastAPI:
    app = FastAPI()
    router = create_auth_router(mock_secrets)
    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestStartAuth:
    @patch("src.google_auth.Flow")
    def test_redirects_to_google(self, mock_flow_cls: MagicMock, client: TestClient) -> None:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?...",
            "random-state",
        )

        response = client.get("/auth/google/start/personal", follow_redirects=False)

        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]


class TestCallback:
    @patch("src.google_auth.Flow")
    def test_stores_token_on_success(
        self, mock_flow_cls: MagicMock, client: TestClient, mock_secrets: MagicMock
    ) -> None:
        mock_flow = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_creds.refresh_token = "refresh-token"
        mock_creds.expiry = None
        mock_flow.credentials = mock_creds

        response = client.get("/auth/google/callback?code=test-auth-code&state=personal")

        assert response.status_code == 200
        assert "personal" in response.json()["message"]
        mock_secrets.set_secret.assert_called_once()
        call_args = mock_secrets.set_secret.call_args
        assert call_args[0][0] == "google-token-personal"
