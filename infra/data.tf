data "azurerm_service_plan" "existing" {
  name                = var.app_service_plan_name
  resource_group_name = var.app_service_plan_rg
}

data "azurerm_communication_service" "existing" {
  name                = var.acs_name
  resource_group_name = var.acs_rg
}
