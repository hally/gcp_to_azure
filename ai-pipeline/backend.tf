terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "tfstateaipipeline"
    container_name       = "tfstate"
    key                  = "ai-pipeline.tfstate"
  }
}
