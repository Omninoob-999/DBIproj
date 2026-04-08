import requests
import base64
import json
import os
import sys

# Allow overriding URL via arg, defaults to docker mapped port 8000
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api/v1/classify_claim"

# Directory containing the test files
TEST_DIR = "test/true_positive"

def get_base64_of_file(filename):
    filepath = os.path.join(TEST_DIR, filename)
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

# Our new payload structure
payload = {
    "request_id": "RQ-69-00103",
    "amount_total": 135200.00,
    "attachments": [],
    "request_documents": [
        {
            "request_document_id": "RQ-69-00103-1",
            "activity": "ค่าโดยสารเครื่องบิน",
            "amount": 135200.00,
            "paid_by": "BEN RUKTANTICHOKE",
            "expense_date_or_commit": "21/01/2026",
            "attachments": [
                {
                    "filename": "E-receipt.pdf",
                    "base64": get_base64_of_file("E-receipt.pdf")
                },
                {
                    "filename": "empeo1.pdf",
                    "base64": get_base64_of_file("empeo1.pdf")
                },
                {
                    "filename": "empeo2.pdf",
                    "base64": get_base64_of_file("empeo2.pdf")
                },
                {
                    "filename": "empeo3.pdf",
                    "base64": get_base64_of_file("empeo3.pdf")
                },
                {
                    "filename": "itinerary.pdf",
                    "base64": get_base64_of_file("itinerary.pdf")
                },
                {
                    "filename": "กำหนดการ.pdf",
                    "base64": get_base64_of_file("กำหนดการ.pdf")
                },
                {
                    "filename": "รายงงานเดินทาง.pdf",
                    "base64": get_base64_of_file("รายงงานเดินทาง.pdf")
                }
            ]
        }
    ]
}

print(f"Sending request to {URL} with true positive data (using gemini)...")
try:
    response = requests.post(URL, json=payload, headers={"Content-Type": "application/json"}, params={"model_provider": "gemini"})
    print(f"Status Code: {response.status_code}")
    
    os.makedirs("test_result", exist_ok=True)
    out_path = os.path.join("test_result", "test_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2, ensure_ascii=False)
        
    print(f"Response successfully written to {out_path}")
    print("Response JSON snippet:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False)[:500] + "\n...")
except Exception as e:
    print(f"Error during request: {e}")
