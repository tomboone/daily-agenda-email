import logging

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class SecretsClient:
    def __init__(self, vault_url: str) -> None:
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, name: str) -> str:
        """Get a secret value. Raises if not found."""
        return self._client.get_secret(name).value  # type: ignore[return-value]

    def get_secret_or_none(self, name: str) -> str | None:
        """Get a secret value, returning None if not found."""
        try:
            return self._client.get_secret(name).value
        except ResourceNotFoundError:
            logger.warning("Secret '%s' not found in Key Vault", name)
            return None

    def set_secret(self, name: str, value: str) -> None:
        """Create or update a secret."""
        self._client.set_secret(name, value)
