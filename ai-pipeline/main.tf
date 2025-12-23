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
  
  skip_provider_registration = true
}

# Resource Group for Terraform State
resource "azurerm_resource_group" "tfstate" {
  name     = "rg-terraform-state"
  location = "East US"
  
  tags = {
    purpose     = "terraform-remote-state"
    project     = "ai-pipeline-migration"
    managed_by  = "terraform"
  }
}

# Storage Account for Terraform State
resource "azurerm_storage_account" "tfstate" {
  name                     = "tfstateaipipeline"
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  tags = {
    purpose = "terraform-state-storage"
  }
}

# Container for State Files
resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}
