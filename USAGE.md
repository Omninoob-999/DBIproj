# API Usage Guide

The **Stateless Extraction Service** uses a `Batch Claim Processing` workflow. Instead of submitting single documents with bespoke schemas, you submit a complete, hierarchical expense claim payload (JSON) where the documents are attached as base64-encoded strings.

The system will automatically classify each document, extract the relevant data natively, and validate the sums against your submitted payload.

You can test this API against your **Local Endpoint** (Docker) or the **Live Azure Endpoint**.

---

## 1. Local Endpoint Testing

**URL:** `http://localhost:8000/api/v1/classify_claim`

### 1a. The Easy Way: Using Python Test Scripts
Because sending raw HTTP requests with massive base64-encoded PDFs is difficult in a terminal, the easiest way to test the API locally is via the provided Python scripts.

1. Ensure the API is running (`docker run --env-file .env -p 8000:8000 extraction-service`).
2. Run the test script:
   ```bash
   python test_true_positive.py
   ```
   *This script constructs a valid `ClaimSubmitRequest` JSON payload, reads the sample PDFs from `test/true_positive/`, encodes them, and fires the request. The full output is saved to `test_result/test_output.json`.*

### 1b. The Hard Way: Using cURL
If you need to test from another system or CLI, you must construct the JSON manually.

```bash
curl -X POST "http://localhost:8000/api/v1/classify_claim?model_provider=gemini" \
     -H "Content-Type: application/json" \
     -d '{
           "request_id": "RQ-69-00103",
           "amount_total": 135200.00,
           "attachments": [],
           "request_documents": [
             {
               "request_document_id": "RQ-69-00103-1",
               "activity": "ค่าโดยสารเครื่องบิน",
               "amount": 135200.00,
               "paid_by": "employee",
               "expense_date_or_commit": "21/01/2026",
               "attachments": [
                 {
                   "filename": "E-receipt.pdf",
                   "base64": "JVBERi0xLjQK..." 
                 }
               ]
             }
           ]
         }'
```

---

## 2. Live Azure Endpoint

**URL:** `https://extract-doc-api.orangerock-6e4091a5.southeastasia.azurecontainerapps.io/api/v1/classify_claim`

> **Note:** The first request to the Azure container may take ~60 seconds to warm up (Cold Start). Subsequent requests will process quickly.

You can target the Live Azure endpoint using the same test script by passing the URL as an argument:

```bash
python test_true_positive.py https://extract-doc-api.orangerock-6e4091a5.southeastasia.azurecontainerapps.io/api/v1/classify_claim
```

---

## Changing Model Providers

The API supports routing the extraction request to different base models. You can control this via the `model_provider` query parameter.

*   `?model_provider=gemini` (Default)
*   `?model_provider=gpt-4o`

*Ensure your `.env` contains the keys for whichever provider you select (`GOOGLE_API_KEY` or `OPENAI_API_KEY`).*
