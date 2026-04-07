import requests
import os
import io
import time

API_URL = "http://localhost:8000/api/v1/classify_claim"

def run_test(test_name: str, files_to_create: dict, expected_class: str):
    print(f"\n--- Running Test: {test_name} ---")
    
    # 1. Create dummy files with text content
    files_payload = []
    temp_files = []
    
    for filename, text_content in files_to_create.items():
        # Create a simple valid image/pdf file extension mock. 
        # The VLM actually uses the filename and bytes. We'll use PDF as the extension.
        path = f"mock_{filename}.pdf"
        temp_files.append(path)
        with open(path, "wb") as f:
            # We just write dummy text. The VLM might be confused if it expects a real PDF,
            # but since we are mocking, let's just use text files and pretend.
            f.write(text_content.encode('utf-8'))
        
        files_payload.append(
            ("files", (path, open(path, "rb"), "application/pdf"))
        )
    
    # 2. Call API
    try:
        print(f"Sending {len(files_payload)} files to API...")
        response = requests.post(API_URL, files=files_payload)
        
        if response.status_code == 200:
            result = response.json()
            actual_class = result.get('claim_category')
            print(f"Result Status: {result.get('status')}")
            print(f"Actual Class: {actual_class}")
            print(f"Expected Class: {expected_class}")
            
            if result.get('missing_documents'):
                print(f"Missing Docs: {result.get('missing_documents')}")
            if result.get('extracted_documents'):
                print(f"Extracted docs: {len(result.get('extracted_documents'))}")
                for doc in result.get('extracted_documents'):
                    print(f"  - {doc.get('filename')}: {doc.get('document_class')} (Receipt Type: {doc.get('receipt_type')})")
                
            if actual_class == expected_class:
                print("✅ Test Passed")
            else:
                print("❌ Test Failed")
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            
    finally:
        # Cleanup
        for _, file_tuple in files_payload:
            file_tuple[1].close()
        for path in temp_files:
            if os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    
    # Wait for API to be up
    print("Wait 2s for API...")
    time.sleep(2)
    
    # Test 1: Airfare (Requires 4 core + Itinerary)
    test1_files = {
        "receipt": "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด Airplane",
        "empeo": "สถาบันข้อมูลขนาดใหญ่ (องค์การมหาชน) เอกสารปฏิบัติงานในประเทศ ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo",
        "report": "รายงานการเดินทางของผู้ปฏิบัติงาน",
        "schedule": "กำหนดการ",
        "itinerary": "Itinerary flight"
    }
    run_test("Airfare Claim", test1_files, "ค่าโดยสารเครื่องบิน")
    
    # Test 2: Taxi (Requires 4 core, receipt must say Taxi)
    test2_files = {
        "receipt": "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด Taxi",
        "empeo": "สถาบันข้อมูลขนาดใหญ่ (องค์การมหาชน) เอกสารปฏิบัติงานในประเทศ ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo",
        "report": "รายงานการเดินทางของผู้ปฏิบัติงาน",
        "schedule": "กำหนดการ"
    }
    run_test("Taxi Claim", test2_files, "ค่ายานพาหนะสาธารณะ Taxi")
    
    # Test 3: Incomplete (Missing Travel Report)
    test3_files = {
        "receipt": "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด Hotel",
        "empeo": "สถาบันข้อมูลขนาดใหญ่ (องค์การมหาชน) เอกสารปฏิบัติงานในประเทศ",
        "schedule": "กำหนดการ",
        "folio": "รายละเอียดการเข้าพัก (Folio)"
    }
    # Should not match Hotel because missing Travel Report
    run_test("Incomplete Hotel Claim", test3_files, "Incomplete or Unmatched")

    print("\nTests complete.")
