variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "ai-pipeline"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "demo"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "East US 2"
}

variable "synapse_admin_password" {
  description = "Admin password for Synapse workspace"
  type        = string
  sensitive   = true
  default     = "P@ssw0rd123!Complex" # Change this!
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    project     = "ai-pipeline-migration"
    environment = "demo"
    managed_by  = "terraform"
    purpose     = "gcp-to-azure-conversion"
  }
}
