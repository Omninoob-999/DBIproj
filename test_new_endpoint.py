import requests
import base64
import json

# Define the endpoint URL
URL = "http://127.0.0.1:8001/api/v1/classify_claim"

# Create a dummy blank image in base64 to test processing
# Small 1x1 png base64
blank_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

# Our new payload structure
payload = {
    "request_id": "RQ-69-00103",
    "amount_total": 4767.00,
    "attachments": [
        {
            "filename": "summary_attachment.png",
            "base64": blank_png_base64
        }
    ],
    "request_documents": [
        {
            "request_document_id": "RQ-69-00103-1",
            "activity": "ค่าใช้จ่ายเดินทางอื่นๆในประเทศ",
            "amount": 456.00,
            "paid_by": "employee, to vendor",
            "expense_date_or_commit": "2023-10-01",
            "attachments": [
                {
                    "filename": "sub_request_1_attachment.png",
                    "base64": blank_png_base64
                }
            ]
        },
        {
            "request_document_id": "RQ-69-00103-2",
            "activity": "ค่าใช้จ่ายเดินทางอื่นๆในประเทศ",
            "amount": 456.00,
            "paid_by": "employee, to vendor",
            "expense_date_or_commit": "2023-10-02",
            "attachments": []
        }
    ]
}

print("Sending request to classify_claim...")
try:
    response = requests.post(URL, json=payload, headers={"Content-Type": "application/json"})
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error during request: {e}")
