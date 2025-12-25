terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Use existing resource group
data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

# Use existing OpenAI service
data "azurerm_cognitive_account" "openai" {
  name                = var.openai_account_name
  resource_group_name = data.azurerm_resource_group.main.name
}

# Container App Environment
resource "azurerm_container_app_environment" "main" {
  name                = "env-echo-openai"
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
}

# Container App
resource "azurerm_container_app" "main" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = data.azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    container {
      name   = "echo-openai-app"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"  # Change after first deploy
      cpu    = 2.0
      memory = "4Gi"

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = data.azurerm_cognitive_account.openai.endpoint
      }

      env {
        name  = "AZURE_OPENAI_KEY"
        value = data.azurerm_cognitive_account.openai.primary_access_key
      }

      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = var.openai_deployment_name
      }

      # Add your other env vars here
      env {
        name  = "SYNAPSE_WORKSPACE"
        value = var.synapse_workspace_name
      }

      env {
        name  = "SQL_POOL"
        value = var.sql_pool_name
      }

      env {
        name  = "DATABASE"
        value = var.database_name
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# Variables
variable "resource_group_name" {
  default = "your-existing-rg"
}

variable "openai_account_name" {
  default = "your-existing-openai"
}

variable "container_app_name" {
  default = "echo-openai-synapse"
}

variable "openai_deployment_name" {
  default = "gpt-4"
}

variable "synapse_workspace_name" {
  default = "your-synapse-workspace"
}

variable "sql_pool_name" {
  default = "your-sql-pool"
}

variable "database_name" {
  default = "master"
}

# Output
output "container_app_url" {
  value = "https://${azurerm_container_app.main.ingress[0].fqdn}"
}
