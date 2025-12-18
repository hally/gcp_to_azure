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
  
  # Credentials come from environment variables
  # GitHub Actions sets these from secrets
  # Locally you can set them or use 'az login'
  
  resource_provider_registrations = "none"
}

# Resource Group
resource "azurerm_resource_group" "example" {
  name     = "rg-pipeline-demo"
  location = "East US"
  
  tags = {
    environment = "dev"
    project     = "gcp-to-azure"
    managed_by  = "terraform"
  }
}
