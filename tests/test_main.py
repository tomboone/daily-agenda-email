from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config import load_config
from src.secrets import SecretsClient

_TEST_CONFIG_YAML = """
send_time: "06:00"
timezone: "America/New_York"
recipient_email: "test@example.com"
sender_email: "noreply@example.com"
google_accounts:
  - name: "personal"
    calendars:
      - id: "primary"
        label: "Personal"
        section: "self"
        filters:
          exclude_titles: []
todoist:
  filters:
    exclude_projects: []
    exclude_titles: []
meal_planning_section_label: "Dinner"
wife_section_label: "Her Schedule"
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(_TEST_CONFIG_YAML)
    return config_file


@pytest.fixture
def mock_secrets() -> MagicMock:
    secrets = MagicMock(spec=SecretsClient)
    secrets.get_secret_or_none.return_value = None
    secrets.get_secret.return_value = "valid-token"
    return secrets


@pytest.fixture
def mock_scheduler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def app(config_file: Path, mock_secrets: MagicMock, mock_scheduler: MagicMock) -> FastAPI:
    from src.main import create_app

    config = load_config(str(config_file))
    return create_app(config, mock_secrets, mock_scheduler)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSendEndpoint:
    @patch("src.main.send_agenda")
    def test_send_requires_token(
        self,
        mock_send: MagicMock,
        client: TestClient,
        mock_secrets: MagicMock,
    ) -> None:
        mock_secrets.get_secret.return_value = "valid-token"

        # No token — should fail
        response = client.post("/send")
        assert response.status_code == 401

        # Wrong token — should fail
        response = client.post("/send", headers={"X-Send-Token": "wrong"})
        assert response.status_code == 401

        # Correct token — should succeed
        response = client.post("/send", headers={"X-Send-Token": "valid-token"})
        assert response.status_code == 200
