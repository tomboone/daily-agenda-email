import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.config import AppConfig, load_config, load_config_from_yaml
from src.google_auth import create_auth_router
from src.scheduler import create_scheduler, send_agenda
from src.secrets import SecretsClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def create_app(
    config: AppConfig,
    secrets: SecretsClient,
    scheduler: object | None = None,
) -> FastAPI:
    """App factory. Accepts pre-built config/secrets/scheduler for testability."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Check for missing Google tokens
        for account in config.google_accounts:
            token = secrets.get_secret_or_none(f"google-token-{account.name}")
            if token is None:
                logger.warning(
                    "No OAuth token for Google account '%s'. "
                    "Visit /auth/google/start/%s to authorize.",
                    account.name,
                    account.name,
                )

        # Start scheduler if provided
        if scheduler is not None and hasattr(scheduler, "start"):
            scheduler.start()  # type: ignore[union-attr]
            logger.info(
                "Scheduler started — daily send at %s %s",
                config.send_time,
                config.timezone,
            )

        yield

        if scheduler is not None and hasattr(scheduler, "shutdown"):
            scheduler.shutdown(wait=False)  # type: ignore[union-attr]
            logger.info("Scheduler shut down")

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    # Register OAuth routes
    auth_router = create_auth_router(secrets)
    app.include_router(auth_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/send")
    async def manual_send(x_send_token: str | None = Header(default=None)) -> dict:
        expected_token = secrets.get_secret("send-endpoint-token")
        if x_send_token is None or x_send_token != expected_token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

        send_agenda(config, secrets)
        return {"message": "Agenda email sent"}

    return app


def build_app_from_env() -> FastAPI:
    """Build the app from environment variables. Used as the uvicorn factory entrypoint."""
    vault_url = os.environ["KEY_VAULT_URL"]
    secrets = SecretsClient(vault_url)

    # Try Key Vault first, fall back to local file
    config_yaml = secrets.get_secret_or_none("app-config")
    if config_yaml is not None:
        config = load_config_from_yaml(config_yaml)
        logger.info("Config loaded from Key Vault secret 'app-config'")
    else:
        config_path = os.environ.get("CONFIG_PATH", "config.yaml")
        config = load_config(config_path)
        logger.info("Config loaded from %s", config_path)

    scheduler = create_scheduler(config, secrets)
    return create_app(config, secrets, scheduler)
