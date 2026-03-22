variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region for all new resources"
  type        = string
  default     = "eastus2"
}

variable "app_service_plan_name" {
  description = "Name of the existing App Service Plan"
  type        = string
}

variable "app_service_plan_rg" {
  description = "Resource group of the existing App Service Plan"
  type        = string
}

variable "acs_name" {
  description = "Name of the existing Azure Communication Services resource"
  type        = string
}

variable "acs_rg" {
  description = "Resource group of the existing ACS resource"
  type        = string
}

variable "ci_principal_id" {
  description = "Object ID of the GitHub Actions OIDC service principal"
  type        = string
}
