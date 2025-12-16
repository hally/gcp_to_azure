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
  
  subscription_id = var.subscription_id
  client_id       = var.client_id
  client_secret   = var.client_secret
  tenant_id       = var.tenant_id
}

# Example: Create a Resource Group
resource "azurerm_resource_group" "example" {
  name     = "rg-pipeline-demo"
  location = "East US"
  
  tags = {
    environment = "dev"
    project     = "gcp-to-azure"
  }
}
