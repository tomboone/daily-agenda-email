data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "rg-daily-agenda-email"
  location = var.location
}

resource "azurerm_key_vault" "main" {
  name                       = "kv-daily-agenda-email"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
}

resource "azurerm_linux_web_app" "main" {
  name                = "daily-agenda-email"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = data.azurerm_service_plan.existing.id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on         = true
    health_check_path = "/health"

    application_stack {
      docker_registry_url = "https://ghcr.io"
      docker_image_name   = "placeholder:latest"
    }
  }

  app_settings = {
    "KEY_VAULT_URL" = azurerm_key_vault.main.vault_uri
    "WEBSITES_PORT" = "8000"
  }

  lifecycle {
    ignore_changes = [
      site_config[0].application_stack[0].docker_registry_url,
      site_config[0].application_stack[0].docker_image_name,
    ]
  }
}

# Web App identity — read/write secrets at runtime (OAuth token refresh)
resource "azurerm_role_assignment" "webapp_keyvault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = azurerm_linux_web_app.main.identity[0].principal_id
}

# Deploying identity — needed so tofu apply can create/update secrets
resource "azurerm_role_assignment" "deployer_keyvault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "random_password" "send_token" {
  length  = 32
  special = false
}

# Intentionally managed by Tofu (no ignore_changes) — config updates via tofu apply
resource "azurerm_key_vault_secret" "app_config" {
  name         = "app-config"
  value        = file("../config.yaml")
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.webapp_keyvault, azurerm_role_assignment.deployer_keyvault]
}

resource "azurerm_key_vault_secret" "google_oauth_client" {
  name         = "google-oauth-client"
  value        = "{}"
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.webapp_keyvault, azurerm_role_assignment.deployer_keyvault]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "todoist_api_token" {
  name         = "todoist-api-token"
  value        = ""
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.webapp_keyvault, azurerm_role_assignment.deployer_keyvault]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "acs_connection_string" {
  name         = "azure-comms-connection-string"
  value        = data.azurerm_communication_service.existing.primary_connection_string
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.webapp_keyvault, azurerm_role_assignment.deployer_keyvault]
}

resource "azurerm_key_vault_secret" "send_endpoint_token" {
  name         = "send-endpoint-token"
  value        = random_password.send_token.result
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.webapp_keyvault, azurerm_role_assignment.deployer_keyvault]
}
