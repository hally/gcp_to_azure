terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }

  skip_provider_registration = true
}

# ========================================
# TERRAFORM STATE STORAGE (Keep this)
# ========================================

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-terraform-state"
  location = var.location

  tags = merge(var.tags, {
    purpose = "terraform-remote-state"
  })
}

resource "azurerm_storage_account" "tfstate" {
  name                     = "tfstateaipipeline"
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = merge(var.tags, {
    purpose = "terraform-state-storage"
  })
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

# ========================================
# AI PIPELINE INFRASTRUCTURE
# ========================================

# Resource Group for AI Pipeline
resource "azurerm_resource_group" "ai_pipeline" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  tags = merge(var.tags, {
    purpose = "ai-pipeline-main-resources"
  })
}

# Storage Account for Prompts and Artifacts
resource "azurerm_storage_account" "pipeline_data" {
  name                     = "aipipeline${var.environment}data"
  resource_group_name      = azurerm_resource_group.ai_pipeline.name
  location                 = azurerm_resource_group.ai_pipeline.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  blob_properties {
    versioning_enabled = true
  }

  tags = merge(var.tags, {
    purpose        = "equivalent-to-gcs-bucket"
    gcp_equivalent = "Cloud Storage"
  })
}

# Container for Prompts
resource "azurerm_storage_container" "prompts" {
  name                  = "prompts"
  storage_account_name  = azurerm_storage_account.pipeline_data.name
  container_access_type = "private"
}

# Container for Artifacts
resource "azurerm_storage_container" "artifacts" {
  name                  = "artifacts"
  storage_account_name  = azurerm_storage_account.pipeline_data.name
  container_access_type = "private"
}

# Get current client config for Key Vault
data "azurerm_client_config" "current" {}

# Key Vault for Secrets
resource "azurerm_key_vault" "pipeline" {
  name                       = "kv-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.ai_pipeline.location
  resource_group_name        = azurerm_resource_group.ai_pipeline.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Purge", "Recover"
    ]
  }

  tags = merge(var.tags, {
    purpose        = "equivalent-to-secret-manager"
    gcp_equivalent = "Secret Manager"
  })
}

# Example Secret - Prompt Blob URI
resource "azurerm_key_vault_secret" "prompt_uri" {
  name         = "prompt-blob-uri"
  value        = "https://${azurerm_storage_account.pipeline_data.name}.blob.core.windows.net/prompts/prompt.txt"
  key_vault_id = azurerm_key_vault.pipeline.id
}

# ========================================
# DATA LAYER - AZURE SYNAPSE
# ========================================

# Storage Account for Synapse (required for Data Lake Gen2)
#resource "azurerm_storage_account" "synapse" {
#  name                     = "synapsepipeline202512"
#  resource_group_name      = azurerm_resource_group.ai_pipeline.name
#  location                 = azurerm_resource_group.ai_pipeline.location
#  account_tier             = "Standard"
#  account_replication_type = "LRS"
#  account_kind             = "StorageV2"
#  is_hns_enabled           = true # Required for Data Lake Gen2
#
#  tags = merge(var.tags, {
#    purpose = "synapse-data-lake"
#  })
#}

# Data Lake Gen2 Filesystem for Synapse
#resource "azurerm_storage_data_lake_gen2_filesystem" "synapse" {
#  name               = "synapse-workspace"
#  storage_account_id = azurerm_storage_account.synapse.id
#}

# Synapse Workspace
#resource "azurerm_synapse_workspace" "pipeline" {
#  name                                 = "synapse-${var.project_name}-${var.environment}"
#  resource_group_name                  = azurerm_resource_group.ai_pipeline.name
#  location                             = azurerm_resource_group.ai_pipeline.location
#  storage_data_lake_gen2_filesystem_id = azurerm_storage_data_lake_gen2_filesystem.synapse.id
#  sql_administrator_login              = "sqladmin"
#  sql_administrator_login_password     = var.synapse_admin_password
#
#  identity {
#    type = "SystemAssigned"
#  }
#
#  tags = merge(var.tags, {
#    purpose        = "equivalent-to-bigquery"
#    gcp_equivalent = "BigQuery"
#  })
#}

# Synapse Firewall Rule - Allow Azure Services
#resource "azurerm_synapse_firewall_rule" "allow_azure_services" {
#  name                 = "AllowAllWindowsAzureIps"
#  synapse_workspace_id = azurerm_synapse_workspace.pipeline.id
#  start_ip_address     = "0.0.0.0"
#  end_ip_address       = "0.0.0.0"
#}

# Synapse Firewall Rule - Allow All (for demo/testing)
#resource "azurerm_synapse_firewall_rule" "allow_all" {
#  name                 = "AllowAll"
#  synapse_workspace_id = azurerm_synapse_workspace.pipeline.id
#  start_ip_address     = "0.0.0.0"
#  end_ip_address       = "255.255.255.255"
#}

# Synapse SQL Pool (Dedicated - for tables)
#resource "azurerm_synapse_sql_pool" "pipeline" {
#  name                 = "call_analytics"
#  synapse_workspace_id = azurerm_synapse_workspace.pipeline.id
#  sku_name             = "DW100c" # Smallest size
#  create_mode          = "Default"
#  storage_account_type = "GRS" # Geo-redundant storage
#
#  tags = merge(var.tags, {
#    purpose = "stores-call-extractions-processed-ledger-vertex-raw"
#  })
#}

# ========================================
# AI SERVICES - AZURE OPENAI
# ========================================

# Azure OpenAI Service
resource "azurerm_cognitive_account" "openai" {
  name                = "openai-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.ai_pipeline.location
  resource_group_name = azurerm_resource_group.ai_pipeline.name
  kind                = "OpenAI"
  sku_name            = "S0"

  tags = merge(var.tags, {
    purpose        = "equivalent-to-vertex-ai-gemini"
    gcp_equivalent = "Vertex AI (Gemini)"
  })
}

# NOTE: Model deployment commented out due to provider schema issues
# You can deploy GPT-4 Turbo manually in the Azure Portal:
# 1. Go to the OpenAI resource
# 2. Click "Model deployments"
# 3. Click "Create new deployment"
# 4. Select gpt-4-turbo model

# # Deploy GPT-4 Turbo Model
# resource "azurerm_cognitive_deployment" "gpt4_turbo" {
#   name                 = "gpt-4-turbo"
#   cognitive_account_id = azurerm_cognitive_account.openai.id
#   
#   model {
#     format  = "OpenAI"
#     name    = "gpt-4"
#     version = "turbo-2024-04-09"
#   }
#   
#   scale {
#     type     = "Standard"
#     capacity = 10
#   }
# }



# ========================================
# APPLICATION LAYER - CONTAINER APPS
# ========================================

# Log Analytics Workspace (required for Container Apps)
resource "azurerm_log_analytics_workspace" "pipeline" {
  name                = "logs-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.ai_pipeline.location
  resource_group_name = azurerm_resource_group.ai_pipeline.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = merge(var.tags, {
    purpose = "centralized-logging"
  })
}

# # Application Insights
# resource "azurerm_application_insights" "pipeline" {
#   name                = "appinsights-${var.project_name}-${var.environment}"
#   location            = azurerm_resource_group.ai_pipeline.location
#   resource_group_name = azurerm_resource_group.ai_pipeline.name
#   workspace_id        = azurerm_log_analytics_workspace.pipeline.id
#   application_type    = "web"
#   
#   tags = merge(var.tags, {
#     purpose = "application-monitoring"
#   })
# }

# Container App Environment
resource "azurerm_container_app_environment" "pipeline" {
  name                       = "cae-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.ai_pipeline.location
  resource_group_name        = azurerm_resource_group.ai_pipeline.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.pipeline.id

  tags = merge(var.tags, {
    purpose = "container-runtime-environment"
  })
}

# Container App (Flask Application)
resource "azurerm_container_app" "flask_processor" {
  name                         = "ca-${var.project_name}-processor"
  container_app_environment_id = azurerm_container_app_environment.pipeline.id
  resource_group_name          = azurerm_resource_group.ai_pipeline.name
  revision_mode                = "Single"

  template {
    container {
      name   = "flask-app"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 2.0
      memory = "4Gi"

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }

      #env {
      #  name  = "SYNAPSE_ENDPOINT"
      #  value = azurerm_synapse_workspace.pipeline.connectivity_endpoints.sql
      #}

      env {
        name  = "STORAGE_ACCOUNT"
        value = azurerm_storage_account.pipeline_data.name
      }

      env {
        name  = "KEY_VAULT_URI"
        value = azurerm_key_vault.pipeline.vault_uri
      }
    }

    min_replicas = 0
    max_replicas = 200
  }

  ingress {
    external_enabled = true
    target_port      = 8080

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = merge(var.tags, {
    purpose        = "equivalent-to-cloud-run"
    gcp_equivalent = "Cloud Run"
  })
}

# ========================================
# ORCHESTRATION - LOGIC APPS
# ========================================

# Logic App Workflow
resource "azurerm_logic_app_workflow" "pipeline_orchestrator" {
  name                = "logic-${var.project_name}-orchestrator"
  location            = azurerm_resource_group.ai_pipeline.location
  resource_group_name = azurerm_resource_group.ai_pipeline.name

  tags = merge(var.tags, {
    purpose        = "equivalent-to-cloud-workflows"
    gcp_equivalent = "Cloud Workflows"
  })
}

# Logic App Trigger - Recurrence (Daily)
resource "azurerm_logic_app_trigger_recurrence" "daily" {
  name         = "daily-trigger"
  logic_app_id = azurerm_logic_app_workflow.pipeline_orchestrator.id
  frequency    = "Day"
  interval     = 1
  start_time   = "2025-01-01T12:00:00Z"
  time_zone    = "Eastern Standard Time"
}
