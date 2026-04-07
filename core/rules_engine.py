import logging
from typing import List, Dict, Any

logger = logging.getLogger("app.core.rules_engine")

def validate_data(extracted_data: dict) -> List[str]:
    """Deterministic checks for financial integrity. (Stage 2: The Controller)"""
    errors = []
    
    if not extracted_data:
        return ["Empty extraction result"]

    # 1. Financial Math Check (New Schema: data.financials.amounts)
    try:
        data_block = extracted_data.get('data', {})
        fin = data_block.get('financials', {})
        amounts = fin.get('amounts', {})
        
        net_amount = amounts.get('net_amount') or 0.0
        tax_amount = amounts.get('tax_amount') or 0.0
        total_amount = amounts.get('total_amount') or 0.0
        
        calculated = round(net_amount + tax_amount, 2)
        if abs(calculated - total_amount) > 0.1:
            errors.append(f"Math Mismatch: Net({net_amount}) + Tax({tax_amount}) != Total({total_amount})")
    except Exception as e:
        errors.append(f"Math check failed: {str(e)}")
    
    # 2. Tax ID Length Check (New Schema: identity.issuer/receiver)
    try:
        identity = extracted_data.get('identity', {})
        for role in ['issuer', 'receiver']:
            entity = identity.get(role, {})
            tax_id = entity.get('tax_id')
            if tax_id:
                clean_tax = str(tax_id).replace("-", "").replace(" ", "")
                # Only warn if it looks like a Thai Tax ID (13 digits) is attempted but wrong length
                if clean_tax.isdigit() and len(clean_tax) != 13:
                     # Some foreign invoices might have diverse tax IDs, so we can be lenient or specific.
                     # For BDI requirements, we expect 13 digits for Thai entities.
                     errors.append(f"Invalid {role} Tax ID length: {tax_id} (Expected 13 digits)")
    except Exception as e:
        errors.append(f"Tax ID check failed: {str(e)}")
            
    return errors

def determine_claim_category(classified_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Stage 2: Takes a list of document classification results and applies the company's checklist matrix
    to determine the final expense claim category.
    """
    # Track what we found
    found_classes = set()
    receipt_types = set()
    
    for doc in classified_docs:
        doc_class = doc.get("document_class")
        if doc_class and doc_class != "Unknown":
            found_classes.add(doc_class)
            
        r_type = doc.get("receipt_type")
        if r_type:
            receipt_types.add(r_type)

    logger.info(f"Rule Engine analyzing found documents: {found_classes}")
    logger.info(f"Rule Engine analyzing receipt types: {receipt_types}")

    # --- Matrix Rules ---
    
    # Check 1: Accommodation (ค่าที่พัก)
    accom_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "รายละเอียดการเข้าพัก (Folio)"
    }
    if accom_required.issubset(found_classes):
        return {"claim_category": "ค่าที่พัก", "missing_documents": [], "status": "COMPLETE"}

    # Check 2: Airfare (ค่าโดยสารเครื่องบิน)
    airfare_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "Itinerary"
    }
    # Note: "ต้นฉบับใบแจ้งหนี้" is optional (marked 'O' in the table), so we don't strictly require it
    if airfare_required.issubset(found_classes):
        return {"claim_category": "ค่าโดยสารเครื่องบิน", "missing_documents": [], "status": "COMPLETE"}

    # Check 3: Allowance (ค่าเบี้ยเลี้ยง)
    allowance_required = {
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "แบบฟอร์มการคำนวณเบี้ยเลี้ยง"
    }
    if allowance_required.issubset(found_classes):
        return {"claim_category": "ค่าเบี้ยเลี้ยง", "missing_documents": [], "status": "COMPLETE"}

    # Check 4: International Phone (ค่าโทรศัพท์เดินทางต่างประเทศ)
    phone_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "รายงานการเดินทาง"
    }
    if phone_required.issubset(found_classes) and "Phone" in receipt_types:
         return {"claim_category": "ค่าโทรศัพท์เดินทางต่างประเทศ", "missing_documents": [], "status": "COMPLETE"}

    # Check 5: Surface Transport Group (Train, Bus, Taxi)
    # They all share the exact same required document checklist!
    transport_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ"
    }
    
    if transport_required.issubset(found_classes):
        # We must rely on the VLM's extraction of the receipt_type to differentiate
        if "Train" in receipt_types:
            return {"claim_category": "ค่ารถไฟ", "missing_documents": [], "status": "COMPLETE"}
        elif "Taxi" in receipt_types:
            return {"claim_category": "ค่ายานพาหนะสาธารณะ Taxi", "missing_documents": [], "status": "COMPLETE"}
        elif "Bus" in receipt_types:
            return {"claim_category": "ค่ายานพาหนะโดยสารประจำทาง", "missing_documents": [], "status": "COMPLETE"}
        else:
            # Fallback if VLM couldn't read the receipt type but we have the transport docs
            return {
                "claim_category": "Unknown Surface Transport", 
                "missing_documents": [], 
                "status": "REQUIRES_MANUAL_REVIEW",
                "message": "Found transport documents but could not determine if Train, Bus, or Taxi from the receipt."
            }

    # If we reach here, the claim is incomplete based on the matrix
    return {
        "claim_category": "Incomplete or Unmatched",
        "missing_documents": ["Unable to determine missing docs due to unmatched base cluster."],
        "status": "INCOMPLETE",
        "found_documents": list(found_classes)
    }
