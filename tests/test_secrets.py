from unittest.mock import MagicMock, patch

from src.secrets import SecretsClient


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_get_secret(mock_cred_cls: MagicMock, mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.get_secret.return_value = MagicMock(value="my-secret-value")
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    result = client.get_secret("test-secret")

    assert result == "my-secret-value"
    mock_client.get_secret.assert_called_once_with("test-secret")


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_set_secret(mock_cred_cls: MagicMock, mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    client.set_secret("test-secret", "new-value")

    mock_client.set_secret.assert_called_once_with("test-secret", "new-value")


@patch("src.secrets.SecretClient")
@patch("src.secrets.DefaultAzureCredential")
def test_get_secret_returns_none_when_not_found(
    mock_cred_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    from azure.core.exceptions import ResourceNotFoundError

    mock_client = MagicMock()
    mock_client.get_secret.side_effect = ResourceNotFoundError("not found")
    mock_client_cls.return_value = mock_client

    client = SecretsClient("https://my-vault.vault.azure.net/")
    result = client.get_secret_or_none("test-secret")

    assert result is None
