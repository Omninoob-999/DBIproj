# Guide: Deploy to Azure

 We will deploy your document extraction API to **Azure Container Apps** (a serverless platform that runs your code) and connect it to **Azure OpenAI**.

We provide **two deployment methods**:
- **Method A**: `az containerapp up` - The easiest approach (builds & deploys in one command)
- **Method B**: Docker Hub - Avoids permission issues by using a public registry

---

## Prerequisites

Before you start, make sure you have these installed:
1.  **Azure CLI**: [Install User Guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
2.  **Docker Desktop** (Required for Method B, optional for Method A): [Install Docker](https://manual.docker.com/)

---

## Phase 1: Setup Azure OpenAI

We need to create the "brain" for your API first, because we need its **Key** and **Endpoint** to give to our application.

1.  **Log in to Azure**
    Open your terminal/command prompt and run:
    ```bash
    az login
    ```
    *A browser window will open. Sign in with your Microsoft account.*

2.  **Create a Resource Group**
    Think of a Resource Group as a "folder" that holds all your project files. We'll name it `rg-extract-poc`.
    ```bash
    az group create --name rg-extract-poc --location southeastasia
    ```
    *(We use `southeastasia` (Singapore) for best speed if you are in Bangkok).*

3.  **Create Azure OpenAI Service**
    *Note: If you don't have access to create OpenAI resources, you might need to apply for access or ask your admin.*
    
    Go to the **[Azure Portal](https://portal.azure.com)**:
    1.  Search for **Azure OpenAI**.
    2.  Click **Create**.
    3.  **Subscription**: Select yours.
    4.  **Resource Group**: Select `rg-extract-poc`.
    5.  **Region**: `Southeast Asia` (or `East US 2` if unavailable).
    6.  **Name**: Give it a unique name (e.g., `aoai-extract-yourname`).
    7.  **Pricing Tier**: Standard S0.
    8.  Click **Next** until **Review + create**, then **Create**.
    
    *Wait for deployment to finish.*

4.  **Deploy the Model (GPT-4o)**
    1.  Go to your new Azure OpenAI resource in the portal.
    2.  Click **"Go to Azure OpenAI Studio"** (button in Overview).
    3.  In Studio, go to **Deployments** (left menu).
    4.  Click **Create new deployment**.
    5.  **Select model**: `gpt-4o`.
    6.  **Model version**: Select the latest (e.g., `2024-08-06` or similar).
    7.  **Deployment name**: `gpt-4o` (Keep this exact, or remember it if you change it).
    8.  Click **Create**.

5.  **Get your Keys**
    1.  Back in the Azure Portal (main view of your OpenAI resource).
    2.  Go to **Keys and Endpoint** (left menu).
    3.  Copy **KEY 1** and the **Endpoint** (e.g., `https://aoai-extract-yourname.openai.azure.com/`).
---

## Phase 2: Deploy Your App

Choose one of the two methods below:

---

### Method A: Using `az containerapp up` (Easiest)

This is the "magic command" that builds your code, creates a registry, and launches the server in one step.

1.  **Navigate to your project folder and install extension**
    ```bash
    az extension add --name containerapp --upgrade
    cd poc-local-api
    ```

    2.  **Run the Deployment Command**
        
        We will read your `.env` file and pass all of its variables directly into the application.
        *(Note: The `$(cat ...)` syntax works in Linux, WSL, and Mac terminal. If you use Windows PowerShell, run this in WSL or Git Bash instead).* 

        ```bash
        az containerapp up \
          --name extract-api \
          --resource-group rg-extract-poc \
          --location southeastasia \
          --source . \
          --ingress external \
          --target-port 8000 \
          --env-vars $(cat .env | grep -v '^#' | xargs)
        ```

    **What this does:**
    *   Creates an Azure Container Registry (to store your app images).
    *   Builds your code into a Docker image.
    *   Creates a Container App Environment.
    *   Deploys your app and exposes it to the internet.

    *This may take 5–10 minutes.*

---

### Method B: Using Docker Hub (Avoids Permission Issues)

If you encounter permission errors with Method A, or if you don't have Owner/User Access Administrator rights, **use Docker Hub instead**. This approach completely avoids RBAC role assignment issues.

#### Why Docker Hub Works Better for Some Users

When you deploy using Azure Container Registry (ACR), the CLI tries to automatically assign the `AcrPull` role to the Container App's managed identity. This requires:

```
Microsoft.Authorization/roleAssignments/write
```

Only users with **Owner** or **User Access Administrator** roles can perform this action. If you don't have these permissions, you'll see:

```
Role assignment failed with error message: (AuthorizationFailed) The client '<your-user>' does not have authorization to perform action 'Microsoft.Authorization/roleAssignments/write'...
```

By using **Docker Hub** (a public registry), you avoid RBAC role assignment entirely. Azure Container Apps can pull public images without extra permissions.

#### Step-by-Step: Deploy from Docker Hub

1.  **Build Your Image Locally**
    Ensure your Dockerfile is in the project root and exposes the correct port (e.g., `EXPOSE 8000`).
    ```bash
    cd poc-local-api
    docker build -t <dockerhub-username>/extract-doc-api:latest .
    ```

2.  **Push to Docker Hub**
    ```bash
    docker login
    docker push <dockerhub-username>/extract-doc-api:latest
    ```

3.  **Create the Container App Environment (if not exists)**
    ```bash
    az containerapp env create \
      --name env-extract-doc-poc \
      --resource-group rg-extract-poc \
      --location southeastasia
    ```

4.  **Create the Container App**
    
    *(Note: Run this in Linux, WSL, or Git Bash for the `.env` extraction to work).* 

    ```bash
    az containerapp create \
      --name extract-doc-api \
      --resource-group rg-extract-poc \
      --environment env-extract-doc-poc \
      --image <dockerhub-username>/extract-doc-api:latest \
      --target-port 8000 \
      --ingress external \
      --env-vars $(cat .env | grep -v '^#' | xargs)
    ```
    
    No `--registry-server` needed because Docker Hub is public.

5.  **Add Secrets for API Keys (Optional)**
    ```bash
    source .env # Load variables
    
    az containerapp secret set \
      --name extract-doc-api \
      --resource-group rg-extract-poc \
      --secrets azure-openai-api-key=$AZURE_OPENAI_API_KEY

    az containerapp update \
      --name extract-doc-api \
      --resource-group rg-extract-poc \
      --set-env-vars AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key
    ```

6.  **Get the App URL**
    ```bash
    az containerapp show \
      --name extract-doc-api \
      --resource-group rg-extract-poc \
      --query properties.configuration.ingress.fqdn \
      --output tsv
    ```

#### Why This Approach Works
- No ACR → No RBAC role assignment.
- No Owner permissions needed.
- Simple and fast deployment.

#### Deployment Flow Diagram
```
[Local Dockerfile] → [Docker Hub] → [Azure Container App]
```

---

## Troubleshooting: Permission Errors

If you used **Method A** and see an error like **"AuthorizationFailed"** with a message about `roleAssignments/write`, you have several options:

### Why this happens
The `az containerapp up` command tries to automatically assign a special permission (called `AcrPull`) that allows your container app to download its code from the Azure Container Registry. This requires **Owner** or **User Access Administrator** role on the Resource Group.

In corporate or organizational Azure accounts, regular users often don't have these elevated permissions.

### Solutions (pick one):

#### Option 1: Switch to Docker Hub (Recommended)
Use **Method B** above. This completely bypasses the permission issue.

#### Option 2: Ask Your Azure Administrator
Contact your Azure administrator and ask them to grant you **Owner** role on the `rg-extract-poc` resource group:
```bash
az role assignment create \
  --assignee <your-email@domain.com> \
  --role Owner \
  --resource-group rg-extract-poc
```

Then re-run the `az containerapp up` command from Method A.

#### Option 3: Manual Role Assignment
If the error message showed a specific `az role assignment create` command, ask your admin to run that exact command. For example:
```bash
az role assignment create \
  --assignee ce690c66-d0b9-4f5e-956e-dd3b0aaa3db7 \
  --scope /subscriptions/.../registries/... \
  --role acrpull
```

After the admin runs this, restart your container app:
```bash
az containerapp revision restart \
  --name extract-api \
  --resource-group rg-extract-poc
```

#### Option 4: Use Azure Portal (Alternative Method)
If you continue to have permission issues, you can deploy using Azure Portal instead:
1. Build your Docker image locally: `docker build -t extract-api .`
2. Use Azure Portal to create Container Apps and Container Registry manually
3. This method requires more steps but gives you more control

---

## Troubleshooting: Datadog `serverless-init` Crashing on Azure

If your container crashes immediately with **exit code 1** and no console log output, and your `Dockerfile` has an `ENTRYPOINT` like:
```dockerfile
ENTRYPOINT ["/usr/local/bin/datadog-init"]
```

This is the root cause.

### Why this happens
Datadog's `serverless-init` binary is designed **exclusively for Google Cloud Run**. On startup, it connects to Google's metadata server (`http://metadata.google.internal`) to retrieve configuration. This server does not exist on Azure Container Apps, so the process exits with code 1 **immediately**, before your Python application even starts.

This causes the container to crash-loop silently — no logs are ever written, because the crash happens before logging is initialized.

### The Fix
Remove the `ENTRYPOINT` and the `COPY` of `datadog-init` from your `Dockerfile`. Datadog APM tracing still works fully on Azure via `ddtrace-run`:

```dockerfile
# ❌ REMOVE these lines (Cloud Run only):
# COPY --from=datadog/serverless-init:1 /datadog-init /usr/local/bin/datadog-init
# ENTRYPOINT ["/usr/local/bin/datadog-init"]

# ✅ KEEP this — works on both local and Azure:
CMD ["ddtrace-run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

With `ddtrace-run`, you still get:
- Full APM tracing
- LLM Observability (LLMObs)
- Automatic instrumentation of FastAPI, OpenAI, requests, etc.
- Log injection and correlation

The only capability you lose is Datadog's Cloud Run-specific log collection agent, which is not applicable to Azure Container Apps anyway.

---

Once the deployment finishes, it will print a URL (e.g., `https://extract-api.gentleground-12345.southeastasia.azurecontainerapps.io`).

1.  **Check Health**
    Open that URL in your browser and add `/docs` at the end (e.g., `https://.../docs`).
    You should see the Swagger UI.

2.  **Test with CURL**
    Run this command in your terminal (update the URL):
    ```bash
    curl -X POST "https://<YOUR_APP_URL>/api/v1/process" \
      -F "file=@/path/to/your/document.pdf;type=application/pdf" \
      -F "schema=$(cat schemas/flight_schema.json)"
    ```
    *(Replace `/path/to/your/document.pdf` with the actual path to a PDF file on your computer).*

---

## Security Note (For Production)

We used **API Keys** here because it is simplest. For a real production app, you should use **Managed Identity** (Passwordless).
*   **Why?** Keys can be stolen. Managed Identity works like an invisible ID badge for your app.
*   **How?** It requires changing your code to use `DefaultAzureCredential` and assigning Roles in Azure. See `BEGINNER-GUIDE-AZURE-DEPLOYMENT-APIM-FRONTDOOR.md` (Step 5) when you are ready for the next level.

---

### TL;DR
- **Try Method A first** - it's the simplest.
- **If you get permission errors**, use **Method B** (Docker Hub) to bypass RBAC issues.
- **If you don't have Owner/User Access Administrator rights**, avoid ACR and use Docker Hub for hassle-free deployment.

---


## How to Update Your App (After Code Changes)

Made changes to your Python code? Here is how to create a new version and update your live app.

### If you used Method A (`az containerapp up`)
Simply run the same "up" command again. Azure will detect the changes, rebuild, and update the app.

```bash
az containerapp up \
  --name extract-api \
  --resource-group rg-extract-poc \
  --source .
```

### If you used Method B (Docker Hub)
You need to build a new image, push it, and tell Azure to download it.

1. **Rebuild**: `docker build -t <your-username>/extract-doc-api:latest .`
2. **Push**: `docker push <your-username>/extract-doc-api:latest`
3. **Update Azure**:
   ```bash
   az containerapp update \
     --name extract-doc-api \
     --resource-group Azure_Resource_Group \
     --image <your-username>/extract-doc-api:latest
   ```
   *(Running this command forces Azure to pull the latest version of your image).*

### Sync Environment Variables from `.env` to Azure

If you've updated your `.env` file (e.g., new API keys or config values), sync them to Azure:

```bash
az containerapp update \
  --name extract-doc-api \
  --resource-group Azure_Resource_Group \
  --set-env-vars $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
```

> [!NOTE]
> This command reads your local `.env` file and updates all environment variables in the Azure Container App in one step. Run this in Linux, WSL, or Git Bash (not Windows PowerShell).

> [!CAUTION]
> This will overwrite all existing environment variables. Make sure your `.env` file contains all variables you want set on Azure, not just the ones you are updating.

---

## Cleanup

To stop paying for these resources, simply delete the resource group:
```bash
az group delete --name rg-extract-poc --yes --no-wait
```
