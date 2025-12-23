output "state_resource_group" {
  value       = azurerm_resource_group.tfstate.name
  description = "Resource group containing Terraform state"
}

output "state_storage_account" {
  value       = azurerm_storage_account.tfstate.name
  description = "Storage account for Terraform state"
}

output "state_container" {
  value       = azurerm_storage_container.tfstate.name
  description = "Container for state files"
}

output "backend_config" {
  value = <<-EOT
    
    To use remote state, add this to your backend.tf:
    
    terraform {
      backend "azurerm" {
        resource_group_name  = "${azurerm_resource_group.tfstate.name}"
        storage_account_name = "${azurerm_storage_account.tfstate.name}"
        container_name       = "${azurerm_storage_container.tfstate.name}"
        key                  = "ai-pipeline.tfstate"
      }
    }
  EOT
  description = "Backend configuration for remote state"
}
