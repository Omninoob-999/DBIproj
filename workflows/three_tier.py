import json
import logging
import telemetry

from config.prompts import EXTRACTOR_SYSTEM_PROMPT, AUDITOR_SYSTEM_PROMPT_TEMPLATE, COMPLIANCE_AUDITOR_PROMPT
from core.parsers import _parse_json_result
from core.rules_engine import validate_data
from clients.vlm_client import _prepare_content_parts, _call_vlm

logger = logging.getLogger("app.workflows.three_tier")

def process_threetier(file_content: bytes, filename: str, model_provider: str = "gemini") -> dict:
    """
    Three-Tier Architecture Implementation:
    1. Extractor Agent
    2. Controller (Validation)
    3. Auditor Agent (Reform)
    """
    tracer = telemetry.get_tracer(__name__)
    with tracer.start_as_current_span("extractor.process_threetier") as span:
        
        # Common: Prepare images
        content_parts = _prepare_content_parts(file_content, filename)
        
        # --- Stage 0: OCR (SKIPPED) ---

        # --- Stage 1: The Extractor ---
        logger.info("Stage 1: Extractor Agent")
        
        extractor_text, extractor_response = _call_vlm(
            EXTRACTOR_SYSTEM_PROMPT, 
            content_parts, 
            model_provider=model_provider,
            prompt_id="tier1-extractor"
        )
        
        try:
            raw_json = _parse_json_result(extractor_text)
        except Exception as e:
            logger.error(f"Stage 1 JSON Parse Error: {e}")
            raise e
            
        # --- Validation (Controller) ---
        logger.info("Validation (Controller)")
        validation_errors = validate_data(raw_json)
        
        final_json = raw_json
        confidence = {"_overall": 1.0, "stage": "extractor", "validation_errors": []}
        
        if validation_errors:
            logger.info(f"Stage 2 Validation Failed: {validation_errors}")
            confidence["validation_errors"] = validation_errors
            confidence["stage"] = "auditor_triggered"
            
            # --- Stage 2: The Auditor ---
            logger.info("Stage 2: Auditor Agent")
            
            auditor_prompt = AUDITOR_SYSTEM_PROMPT_TEMPLATE.format(errors=json.dumps(validation_errors))
            
            auditor_text, auditor_response = _call_vlm(
                auditor_prompt, 
                content_parts, 
                model_provider=model_provider,
                prompt_id="tier2-auditor-reform"
            )
            
            try:
                auditor_json = _parse_json_result(auditor_text)
                
                # MERGE auditor corrections into raw_json
                def recursive_update(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict):
                            d[k] = recursive_update(d.get(k, {}), v)
                        else:
                            d[k] = v
                    return d
                
                final_json = recursive_update(raw_json, auditor_json)
                confidence["auditor_correction"] = True
                
            except Exception as e:
                logger.error(f"Stage 3 Auditor Error: {e}")
                confidence["auditor_error"] = str(e)
        else:
            logger.info("Stage 2 Validation Passed")
            confidence["stage"] = "verified"

        # --- Stage 3: Compliance Auditor ---
        logger.info("Stage 3: Compliance Auditor Agent")
        
        try:
            compliance_prompt = COMPLIANCE_AUDITOR_PROMPT.replace("{extracted_json}", json.dumps(final_json, ensure_ascii=False))
            
            audit_text, _ = _call_vlm(
                compliance_prompt, 
                content_parts, 
                model_provider=model_provider,
                prompt_id="tier3-compliance-auditor"
            )
            
            audit_json = _parse_json_result(audit_text)
            
            if isinstance(audit_json, dict) and "compliance_audit" in audit_json:
                final_json["compliance_audit"] = audit_json["compliance_audit"]
            else:
                 logger.warning(f"Stage 3 returned unexpected format: {audit_json}")
                 final_json["compliance_audit"] = ["[WARNING] Auditor Agent failed to return valid format"]

        except Exception as e:
            logger.error(f"Stage 3 Compliance Audit Failed: {e}")
            final_json["compliance_audit"] = [f"[WARNING] Auditor Agent Error: {str(e)}"]

        return {"extraction": final_json, "confidence": confidence}

def process_document(file_content: bytes, filename: str, model_provider: str = "gemini"):
    """
    Main entry point for document extraction.
    """
    return process_threetier(file_content, filename, model_provider="gemini")
