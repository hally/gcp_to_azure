# ========================================
# TERRAFORM STATE OUTPUTS
# ========================================

output "state_resource_group" {
  value       = azurerm_resource_group.tfstate.name
  description = "Resource group containing Terraform state"
}

output "state_storage_account" {
  value       = azurerm_storage_account.tfstate.name
  description = "Storage account for Terraform state"
}

# ========================================
# AI PIPELINE OUTPUTS
# ========================================

output "ai_pipeline_resource_group" {
  value       = azurerm_resource_group.ai_pipeline.name
  description = "Main resource group for AI pipeline"
}

output "pipeline_storage_account" {
  value       = azurerm_storage_account.pipeline_data.name
  description = "Storage account for prompts and artifacts"
}

output "key_vault_name" {
  value       = azurerm_key_vault.pipeline.name
  description = "Key Vault for secrets"
}

output "key_vault_uri" {
  value       = azurerm_key_vault.pipeline.vault_uri
  description = "Key Vault URI"
}

# ========================================
# DATA LAYER OUTPUTS
# ========================================
#
#output "synapse_workspace_name" {
#  value       = azurerm_synapse_workspace.pipeline.name
#  description = "Synapse workspace name"
#}

#output "synapse_sql_endpoint" {
#  value       = azurerm_synapse_workspace.pipeline.connectivity_endpoints.sql
#  description = "Synapse SQL endpoint"
#}

#output "synapse_sql_pool" {
#  value       = azurerm_synapse_sql_pool.pipeline.name
#  description = "Synapse SQL Pool name"
#}

# ========================================
# AI SERVICES OUTPUTS
# ========================================

output "openai_endpoint" {
  value       = azurerm_cognitive_account.openai.endpoint
  description = "Azure OpenAI endpoint"
}

# output "openai_model_deployment" {
#   value       = azurerm_cognitive_deployment.gpt4_turbo.name
#   description = "Deployed GPT-4 Turbo model name"
# }

# ========================================
# APPLICATION LAYER OUTPUTS
# ========================================

output "container_app_url" {
  value       = "https://${azurerm_container_app.flask_processor.ingress[0].fqdn}"
  description = "Container App URL"
}

output "log_analytics_workspace" {
  value       = azurerm_log_analytics_workspace.pipeline.name
  description = "Log Analytics workspace"
}

# ========================================
# ORCHESTRATION OUTPUTS
# ========================================

output "logic_app_name" {
  value       = azurerm_logic_app_workflow.pipeline_orchestrator.name
  description = "Logic App workflow name"
}

# ========================================
# ARCHITECTURE SUMMARY
# ========================================

output "architecture_summary" {
  value       = <<-EOT
    
    ╔════════════════════════════════════════════════════════════╗
    ║       AI Pipeline Infrastructure - COMPLETE                 ║
    ╚════════════════════════════════════════════════════════════╝
    
    📦 RESOURCE GROUP
       Name: ${azurerm_resource_group.ai_pipeline.name}
       Location: ${azurerm_resource_group.ai_pipeline.location}
    
    💾 STORAGE
       Data Storage: ${azurerm_storage_account.pipeline_data.name}
          
    🤖 AI SERVICES (Vertex AI equivalent)
       OpenAI Service: ${azurerm_cognitive_account.openai.name}
       Endpoint: ${azurerm_cognitive_account.openai.endpoint}
       Model: (Deploy manually - see OpenAI resource)
    
    🐳 APPLICATION (Cloud Run equivalent)
       Container App: ${azurerm_container_app.flask_processor.name}
       URL: https://${azurerm_container_app.flask_processor.ingress[0].fqdn}
    
    🔐 SECURITY
       Key Vault: ${azurerm_key_vault.pipeline.name}
    
    📊 MONITORING
       Log Analytics: ${azurerm_log_analytics_workspace.pipeline.name}
    
    🔄 ORCHESTRATION (Cloud Workflows equivalent)
       Logic App: ${azurerm_logic_app_workflow.pipeline_orchestrator.name}
    
    ╔════════════════════════════════════════════════════════════╗
    ║  GCP → Azure Service Mapping Complete!                     ║
    ╚════════════════════════════════════════════════════════════╝
  EOT
  description = "Complete infrastructure summary"
}
