import json
import logging
from datetime import date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from google.oauth2.credentials import Credentials

from src.config import AppConfig
from src.email import compose_email, send_email
from src.google_calendar import CalendarEvent, fetch_events_for_account
from src.secrets import SecretsClient
from src.todoist import fetch_tasks

logger = logging.getLogger(__name__)


def _load_google_credentials(account_name: str, secrets: SecretsClient) -> Credentials | None:
    """Load Google OAuth credentials from Key Vault for an account."""
    token_json = secrets.get_secret_or_none(f"google-token-{account_name}")
    if token_json is None:
        logger.warning("No token found for Google account '%s'", account_name)
        return None

    oauth_json = secrets.get_secret("google-oauth-client")
    oauth = json.loads(oauth_json)
    token = json.loads(token_json)

    return Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
    )


def send_agenda(config: AppConfig, secrets: SecretsClient) -> None:
    """Fetch all data, compose the email, and send it."""
    tz = ZoneInfo(config.timezone)
    today = date.today()

    all_events: list[CalendarEvent] = []
    for account in config.google_accounts:
        creds = _load_google_credentials(account.name, secrets)
        if creds is None:
            continue
        original_token = creds.token
        try:
            events = fetch_events_for_account(account, creds, today, tz)
            all_events.extend(events)

            # Only write back if the token was actually refreshed
            if creds.token != original_token:
                token_data = json.dumps(
                    {
                        "access_token": creds.token,
                        "refresh_token": creds.refresh_token,
                        "expiry": creds.expiry.isoformat() if creds.expiry else None,
                    }
                )
                secrets.set_secret(f"google-token-{account.name}", token_data)
                logger.info("Refreshed token saved for account '%s'", account.name)
        except Exception:
            logger.exception("Failed to fetch events for account '%s'", account.name)

    tasks = []
    try:
        todoist_token = secrets.get_secret("todoist-api-token")
        tasks = fetch_tasks(todoist_token, config.todoist.filters, today)
    except Exception:
        logger.exception("Failed to fetch Todoist tasks")

    subject, html = compose_email(
        events=all_events,
        tasks=tasks,
        today=today,
        timezone=config.timezone,
        meal_planning_section_label=config.meal_planning_section_label,
        wife_section_label=config.wife_section_label,
    )

    try:
        conn_string = secrets.get_secret("azure-comms-connection-string")
        send_email(
            connection_string=conn_string,
            sender=config.sender_email,
            recipient=config.recipient_email,
            subject=subject,
            html_body=html,
        )
        logger.info("Daily agenda email sent successfully")
    except Exception:
        logger.exception("Failed to send daily agenda email")


def create_scheduler(config: AppConfig, secrets: SecretsClient) -> BackgroundScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BackgroundScheduler()
    hour, minute = config.send_time.split(":")

    trigger = CronTrigger(
        hour=int(hour),
        minute=int(minute),
        timezone=ZoneInfo(config.timezone),
    )

    scheduler.add_job(
        send_agenda,
        trigger=trigger,
        args=[config, secrets],
        name="send_agenda",
    )

    return scheduler
