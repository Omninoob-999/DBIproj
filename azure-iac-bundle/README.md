
# Azure IaC Bundle (Bicep + Terraform)

This bundle provisions a production-ready skeleton for your Stateless Extraction API on Azure:

- Azure Container Apps (FastAPI) + autoscale (HTTP concurrency)
- Azure Container Registry
- Azure Key Vault (RBAC)
- Log Analytics + Application Insights (OpenTelemetry-ready)
- Azure API Management (internal VNET)
- Azure Front Door Premium (skeleton)
- Private Endpoint to Azure OpenAI
- VNet + subnets for APIM and Private Endpoints

**Default region:** `southeastasia`

## Deploy (Bicep)
```bash
az group create -n rg-extract -l southeastasia
az deployment group create -g rg-extract -f bicep/main.bicep -p @bicep/parameters.example.json
```

## Deploy (Terraform)
```bash
cd terraform
terraform init
terraform apply -auto-approve
```
