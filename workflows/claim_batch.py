import json
import logging
from typing import List, Dict, Any

from config.prompts import CLASSIFIER_SYSTEM_PROMPT, COMPLIANCE_AUDITOR_PROMPT
from core.parsers import _parse_json_result
from core.rules_engine import determine_claim_category
from clients.vlm_client import _prepare_content_parts, _call_vlm

logger = logging.getLogger("app.workflows.claim_batch")

def _classify_and_extract_document(file_content: bytes, filename: str, model_provider: str = "gemini") -> Dict[str, Any]:
    """
    Stage 1: Sends a single document to the VLM to classify it.
    """
    try:
        content_parts = _prepare_content_parts(file_content, filename)
        
        raw_result, _ = _call_vlm(
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            content_parts=content_parts,
            model_provider=model_provider,
            prompt_id="doc-classifier"
        )
        
        parsed_json = _parse_json_result(raw_result)

        if parsed_json.get("document_class") == "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด":
            logger.info("Stage 3: Compliance Auditor Agent for receipt")
            try:
                compliance_prompt = COMPLIANCE_AUDITOR_PROMPT.replace("{extracted_json}", json.dumps(parsed_json, ensure_ascii=False))
                
                audit_text, _ = _call_vlm(
                    compliance_prompt, 
                    content_parts, 
                    model_provider=model_provider,
                    prompt_id="tier3-compliance-auditor"
                )
                
                audit_json = _parse_json_result(audit_text)
                
                if isinstance(audit_json, dict) and "compliance_audit" in audit_json:
                    parsed_json["compliance_audit"] = audit_json["compliance_audit"]
                else:
                     logger.warning(f"Stage 3 returned unexpected format: {audit_json}")
                     parsed_json["compliance_audit"] = ["[WARNING] Auditor Agent failed to return valid format"]

            except Exception as e:
                logger.error(f"Stage 3 Compliance Audit Failed: {e}")
                parsed_json["compliance_audit"] = [f"[WARNING] Auditor Agent Error: {str(e)}"]

        return parsed_json
        
    except Exception as e:
        logger.error(f"Error classifying document {filename}: {e}")
        return {"document_class": "Unknown", "receipt_type": None, "error": str(e)}

def extract_total_amount(doc_result: dict) -> float:
    try:
        doc_class = doc_result.get("document_class")
        val = 0.0
        if doc_class == "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด":
            val = doc_result.get("total_amount")
        elif doc_class == "แบบฟอร์มการคำนวณเบี้ยเลี้ยง":
            val = doc_result.get("allowance_details", {}).get("summary", {}).get("total_amount")
        elif doc_class == "ต้นฉบับใบแจ้งหนี้":
            val = doc_result.get("invoice_details", {}).get("total_amount")
        elif doc_class == "รายละเอียดการเข้าพัก (Folio)":
            val = doc_result.get("folio_details", {}).get("total_charges")
        
        if val is None:
            return 0.0
            
        if isinstance(val, str):
            val = val.replace(',', '')
            return float(val)
        return float(val)
    except Exception as e:
        logger.error(f"Error extracting total amount: {e}")
        return 0.0

def process_claim_batch(file_contents: List[bytes], filenames: List[str], payload: dict = None, model_provider: str = "gemini") -> dict:
    """
    Orchestrates the classification and extraction of a batch of documents, 
    then applies the deterministic rule logic to evaluate the batch,
    and validates against the incoming API payload.
    """
    classified_docs = []
    
    # 1. Classify each document individually using VLM
    for idx, content in enumerate(file_contents):
        filename = filenames[idx]
        logger.info(f"Classifying {filename}...")
        
        doc_result = _classify_and_extract_document(content, filename, model_provider)
        doc_result['filename'] = filename # append tracking meta
        classified_docs.append(doc_result)
    
    # 2. Apply Rule Engine to determine final category
    final_decision = determine_claim_category(classified_docs)
    
    # 2.5 Ensure validation against payload
    validation_results = []
    is_valid = True
    
    if payload:
        # Validate global amount_total
        expected_total = float(payload.get("amount_total", 0.0))
        extracted_total_amount = sum(extract_total_amount(doc) for doc in classified_docs)
        if abs(expected_total - extracted_total_amount) > 0.1:
            is_valid = False
            validation_results.append({
                "level": "error",
                "message": f"Global Amount Mismatch: Payload total {expected_total} != Extracted total {extracted_total_amount:.2f}"
            })

        # Validate nested documents (Request Documents)
        for req_doc in payload.get('request_documents', []):
            req_id = req_doc.get('request_document_id')
            req_activity = req_doc.get('activity')
            req_amount = float(req_doc.get('amount', 0.0))
            
            # Find classified docs that belong to this sub-request
            nested_docs = [doc for doc in classified_docs if str(doc.get('filename', '')).startswith(f"{req_id}_")]
            
            if not nested_docs:
                continue
                
            # Check nested amount
            nested_extracted_amount = sum(extract_total_amount(doc) for doc in nested_docs)
            if abs(req_amount - nested_extracted_amount) > 0.1:
                is_valid = False
                validation_results.append({
                    "level": "error",
                    "request_document_id": req_id,
                    "message": f"Amount Mismatch: Sub-request amount {req_amount} != Extracted amount {nested_extracted_amount:.2f}"
                })
                
            # Check Activity matches extracted document classes or category
            extracted_classes = [doc.get('document_class') for doc in nested_docs]
            nested_decision = determine_claim_category(nested_docs)
            nested_claim_cat = nested_decision.get('claim_category')
            
            if req_activity not in extracted_classes and req_activity != nested_claim_cat:
                is_valid = False
                validation_results.append({
                    "level": "error",
                    "request_document_id": req_id,
                    "message": f"Activity Mismatch: Payload activity '{req_activity}' does not match extracted classes {extracted_classes} or category '{nested_claim_cat}'"
                })

    # 3. Create top hierarchy JSON response combining final decision + doc details
    status_str = final_decision.get("status", "ERROR")
    if payload and not is_valid:
        status_str = "VALIDATION_FAILED"
        
    return {
        "claim_category": final_decision.get("claim_category", "Unknown"),
        "missing_documents": final_decision.get("missing_documents", []),
        "status": status_str,
        "message": final_decision.get("message", "Processed successfully."),
        "validation_results": validation_results,
        "extracted_documents": classified_docs
    }

