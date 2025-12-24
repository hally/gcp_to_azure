# Azure AI Pipeline Infrastructure

A complete Azure infrastructure implementation demonstrating cloud migration from GCP to Azure using Infrastructure as Code (Terraform).

## 🎯 Project Overview

This project showcases the architecture and provisioning of an AI-powered call analytics pipeline on Microsoft Azure, designed as an equivalent to a Google Cloud Platform implementation. The infrastructure is fully defined using Terraform, following cloud engineering best practices.

## 🏗️ Architecture

### Azure Services Deployed

| Azure Service | GCP Equivalent | Purpose |
|---------------|----------------|---------|
| **Azure OpenAI** | Vertex AI (Gemini) | AI/ML processing with GPT-4 |
| **Azure Container Apps** | Cloud Run | Containerized application hosting |
| **Azure Storage** | Cloud Storage | Data and artifact storage |
| **Azure Key Vault** | Secret Manager | Secrets management |
| **Azure Logic Apps** | Cloud Workflows | Workflow orchestration |
| **Log Analytics** | Cloud Logging | Centralized logging and monitoring |

### Infrastructure Components

┌─────────────────────────────────────────────────────────────┐ │                  Azure Resource Group                        │ │                 rg-ai-pipeline-demo                          │ ├─────────────────────────────────────────────────────────────┤ │                                                               │ │  ┌──────────────────┐         ┌──────────────────┐          │ │  │  Logic App       │────────▶│ Container App    │          │ │  │  (Orchestration) │         │ (Flask Processor)│          │ │  └──────────────────┘         └────────┬─────────┘          │ │                                        │                     │ │                                        ▼                     │ │                              ┌──────────────────┐           │ │                              │  Azure OpenAI    │           │ │                              │  (GPT-4)         │           │ │                              └──────────────────┘           │ │                                        │                     │ │         ┌──────────────────────────────┴─────────┐          │ │         ▼                              ▼         │          │ │  ┌──────────────────┐         ┌──────────────────┐          │ │  │  Blob Storage    │         │  Key Vault       │          │ │  │  (Data/Prompts)  │         │  (Secrets)       │          │ │  └──────────────────┘         └──────────────────┘          │ │                                                               │ │  ┌──────────────────────────────────────────┐              │ │  │  Log Analytics                            │              │ │  │  (Monitoring & Logging)                   │              │ │  └──────────────────────────────────────────┘              │ └─────────────────────────────────────────────────────────────┘


## 🚀 Features

- **Infrastructure as Code**: Complete infrastructure defined in Terraform
- **Remote State Management**: Terraform state stored in Azure Blob Storage
- **Multi-Cloud Knowledge**: Demonstrates GCP to Azure service mapping
- **Security Best Practices**: Secrets managed via Azure Key Vault
- **Monitoring**: Centralized logging with Azure Log Analytics
- **Scalability**: Container Apps with auto-scaling (0-200 instances)
- **CI/CD Ready**: GitHub Actions workflow for automated deployments

## 📁 Project Structure

gcp-to-azure-pipeline/ 
├── .github/ 
│   └── workflows/ │       
                   └── terraform.yml          
# GitHub Actions CI/CD 
├── ai-pipeline/ 
│   
├── backend.tf                 
# Remote state configuration 
│   
├── main.tf                    
# Infrastructure resources 
│   
├── variables.tf               
# Variable definitions 
                    │   
                    └── outputs.tf                 
# Output values 
├── .gitignore 
└── README.md


## 🛠️ Technologies Used

- **Terraform** - Infrastructure as Code
- **Azure CLI** - Azure resource management
- **GitHub Actions** - CI/CD automation
- **Azure Resource Manager** - Azure provider for Terraform

## 📋 Prerequisites

- Azure subscription
- Terraform >= 1.6.0
- Azure CLI
- Git

## 🔧 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/hally/gcp-to-azure-pipeline.git
cd gcp-to-azure-pipeline/ai-pipeline

# Login to Azure
az login

# Set subscription (if you have multiple)
az account set --subscription "YOUR_SUBSCRIPTION_ID"

az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Logic

terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply

🔐 Security Considerations
Secrets Management: All sensitive data stored in Azure Key Vault
Network Security: Firewall rules configured for Azure services
Access Control: Managed identities for service-to-service authentication
State Security: Remote state stored in private blob storage

💰 Cost Management
Estimated monthly cost: ~$50-100 (depending on usage)

To minimize costs:

Container Apps scale to zero when not in use
Use smallest SKUs for demo/testing
Destroy resources when not needed: terraform destroy

📊 Deployed Resources
Resource Type	Name	                        Purpose
Resource Group	rg-ai-pipeline-demo	            Container for all resources
Storage Account	aipipelinedemodata	            Data and prompt storage
OpenAI Service	openai-ai-pipeline-demo	        AI processing
Container App	ca-ai-pipeline-processor	    Application runtime
Key Vault	    kv-ai-pipeline-demo	            Secrets management
Log Analytics	logs-ai-pipeline-demo	        Monitoring
Logic App	    logic-ai-pipeline-orchestrator	Workflow automation

🔄 CI/CD Pipeline
GitHub Actions workflow automatically:

✅ Validates Terraform code
✅ Checks formatting
✅ Runs terraform plan on pull requests
✅ Applies changes on merge to main
🌟 Future Enhancements
 Add Azure Synapse Analytics for data warehousing
 Implement Azure Application Insights for detailed monitoring
 Deploy GPT-4 model via Terraform
 Add Azure Service Bus for event-driven architecture
 Implement Azure Front Door for global distribution
📝 Notes
This is a demonstration project showcasing cloud architecture and IaC skills. Some resources (like Synapse) were omitted due to regional capacity constraints during development, but the architecture design accounts for them.

🤝 Contributing
This is a personal learning project, but feedback and suggestions are welcome!

📄 License
This project is open source and available under the MIT License.

👤 Author
Hamza Ally
LinkedIn: https://www.linkedin.com/in/hamzaally/
GitHub: @hally

🙏 Acknowledgments
Microsoft Azure Documentation
HashiCorp Terraform Documentation
Cloud engineering best practices from the community
