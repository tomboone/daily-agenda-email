import json
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from src.config import AppConfig
from src.scheduler import create_scheduler, send_agenda


class TestSendAgenda:
    @patch("src.scheduler.send_email")
    @patch("src.scheduler.compose_email")
    @patch("src.scheduler.fetch_tasks")
    @patch("src.scheduler.fetch_events_for_account")
    @patch("src.scheduler.Credentials")
    def test_orchestrates_full_send(
        self,
        mock_creds_cls: MagicMock,
        mock_fetch_events: MagicMock,
        mock_fetch_tasks: MagicMock,
        mock_compose: MagicMock,
        mock_send: MagicMock,
        sample_config: AppConfig,
    ) -> None:
        secrets = MagicMock()
        secrets.get_secret.side_effect = lambda name: {
            "google-token-personal": json.dumps(
                {
                    "access_token": "at",
                    "refresh_token": "rt",
                    "expiry": None,
                }
            ),
            "google-token-work": json.dumps(
                {
                    "access_token": "at2",
                    "refresh_token": "rt2",
                    "expiry": None,
                }
            ),
            "google-oauth-client": json.dumps(
                {
                    "client_id": "cid",
                    "client_secret": "csec",
                }
            ),
            "todoist-api-token": "todoist-token",
            "azure-comms-connection-string": "conn-string",
        }[name]
        secrets.get_secret_or_none.side_effect = lambda name: secrets.get_secret(name)

        mock_fetch_events.return_value = []
        mock_fetch_tasks.return_value = []
        mock_compose.return_value = ("Subject", "<html>body</html>")

        send_agenda(sample_config, secrets)

        assert mock_fetch_events.call_count == 2
        mock_fetch_tasks.assert_called_once()
        mock_compose.assert_called_once()
        mock_send.assert_called_once()

    @patch("src.scheduler.send_email")
    @patch("src.scheduler.compose_email")
    @patch("src.scheduler.fetch_tasks")
    @patch("src.scheduler.fetch_events_for_account")
    @patch("src.scheduler.Credentials")
    def test_logs_error_on_missing_token(
        self,
        mock_creds_cls: MagicMock,
        mock_fetch_events: MagicMock,
        mock_fetch_tasks: MagicMock,
        mock_compose: MagicMock,
        mock_send: MagicMock,
        sample_config: AppConfig,
    ) -> None:
        secrets = MagicMock()
        secrets.get_secret_or_none.return_value = None
        secrets.get_secret.side_effect = lambda name: {
            "todoist-api-token": "todoist-token",
            "azure-comms-connection-string": "conn-string",
            "google-oauth-client": json.dumps({"client_id": "cid", "client_secret": "csec"}),
        }.get(name, None)

        mock_fetch_tasks.return_value = []
        mock_compose.return_value = ("Subject", "<html></html>")

        send_agenda(sample_config, secrets)
        mock_compose.assert_called_once()

    @patch("src.scheduler.send_email")
    @patch("src.scheduler.compose_email")
    @patch("src.scheduler.fetch_tasks")
    @patch("src.scheduler.fetch_events_for_account")
    @patch("src.scheduler.Credentials")
    def test_sends_reauth_notification_on_refresh_error(
        self,
        mock_creds_cls: MagicMock,
        mock_fetch_events: MagicMock,
        mock_fetch_tasks: MagicMock,
        mock_compose: MagicMock,
        mock_send: MagicMock,
        sample_config: AppConfig,
    ) -> None:
        secrets = MagicMock()
        secrets.get_secret.side_effect = lambda name: {
            "google-token-personal": json.dumps(
                {"access_token": "at", "refresh_token": "rt", "expiry": None}
            ),
            "google-token-work": json.dumps(
                {"access_token": "at2", "refresh_token": "rt2", "expiry": None}
            ),
            "google-oauth-client": json.dumps({"client_id": "cid", "client_secret": "csec"}),
            "todoist-api-token": "todoist-token",
            "azure-comms-connection-string": "conn-string",
        }[name]
        secrets.get_secret_or_none.side_effect = lambda name: secrets.get_secret(name)

        # First account succeeds, second raises RefreshError
        mock_fetch_events.side_effect = [
            [],
            RefreshError("Token has been expired or revoked."),
        ]
        mock_fetch_tasks.return_value = []
        mock_compose.return_value = ("Subject", "<html>body</html>")

        send_agenda(sample_config, secrets)

        # Agenda email + reauth notification
        assert mock_send.call_count == 2
        reauth_call = mock_send.call_args_list[1]
        assert "Re-authorization" in reauth_call.kwargs.get(
            "subject", reauth_call[1].get("subject", "")
        ) or "Re-authorization" in str(reauth_call)
        assert "work" in str(reauth_call)


class TestCreateScheduler:
    def test_creates_scheduler_with_cron_trigger(self, sample_config: AppConfig) -> None:
        secrets = MagicMock()
        scheduler = create_scheduler(sample_config, secrets)

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].name == "send_agenda"
