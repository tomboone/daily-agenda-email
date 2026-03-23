import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from src.secrets import SecretsClient

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def create_auth_router(secrets: SecretsClient) -> APIRouter:
    """Create the Google OAuth router with the given secrets client."""
    router = APIRouter(prefix="/auth/google")
    _pending_verifiers: dict[str, str] = {}

    def _get_client_config() -> dict:
        raw = secrets.get_secret("google-oauth-client")
        parsed = json.loads(raw)
        return {
            "web": {
                "client_id": parsed["client_id"],
                "client_secret": parsed["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    @router.get("/start/{account_name}")
    async def start_auth(account_name: str, request: Request) -> RedirectResponse:
        """Redirect to Google's consent screen."""
        redirect_uri = str(request.url_for("auth_callback"))
        client_config = _get_client_config()

        flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=account_name,
        )
        if flow.code_verifier is not None:
            _pending_verifiers[account_name] = flow.code_verifier
        return RedirectResponse(url=auth_url)

    @router.get("/callback", name="auth_callback")
    async def auth_callback(code: str, state: str, request: Request) -> dict:
        """Handle the OAuth callback from Google."""
        redirect_uri = str(request.url_for("auth_callback"))
        client_config = _get_client_config()

        flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
        flow.code_verifier = _pending_verifiers.pop(state, None)
        flow.fetch_token(code=code)

        creds = flow.credentials
        token_data = json.dumps(
            {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
        )

        secret_name = f"google-token-{state}"
        secrets.set_secret(secret_name, token_data)
        logger.info("Stored OAuth token for account '%s'", state)

        return {"message": f"Successfully authorized account '{state}'"}

    return router
