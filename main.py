import asyncio
import shutil
import tempfile
import os
import time
from venv import logger
import phoenix

from typing import List
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import base64

from workflows.three_tier import process_document as three_tier_process_document
from workflows.claim_batch import process_claim_batch
from phoenix.otel import register
import logging
load_dotenv()
# Ensure standard formatting for the main application
logging.basicConfig(level=logging.INFO)
session = phoenix.launch_app()

logger = logging.getLogger("app.main")

#Phoenix Otel Tracing
tracer_provider = register(project_name="BDI_ProcessDocs", auto_instrument=True)

app = FastAPI(title="Stateless Extraction Service POC")

# Create a dedicated pool for heavy computation
# limit max_workers to prevent CPU thrashing
process_pool = ProcessPoolExecutor(max_workers=os.cpu_count())


class ExtractionResponse(BaseModel):
    status: str
    metadata_echo: Optional[str] = None
    extracted_data: Dict[str, Any]


def core_extraction_logic(file_path: str, filename: str, extractor_type: str = "gemini") -> dict:
    """
    CPU-BOUND BLOCK: This runs in a separate process.
    """
    # Re-initialize telemetry for this worker process
    #telemetry.setup_telemetry()
    worker_logger = logging.getLogger("app.worker")

    try:
        # Read file content from temp path
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Process
        # Execute the heavy VLM + parsing logic synchronously
        # We assume the extraction function inside workflow knows how to handle the logic.
        result = three_tier_process_document(file_content, filename, extractor_type)
        return result
    except Exception as e:
        worker_logger.error(f"Extraction Error: {e}")
        import traceback
        traceback.print_exc()
        raise e


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/v1/process", response_model=ExtractionResponse)
async def process_document(
    file: UploadFile = File(...),
    meta_data: Optional[str] = Form(None),
    extractor_type: str = Form("gemini", description="One of 'gemini' (default) or 'threetier'")
):
    # Validation: Check file type
    # Allow pdf, png, jpeg, webp, gif
    if file.content_type not in ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"]:
        # Also check filename extension as fallback
        ext = file.filename.lower().split('.')[-1]
        if ext not in ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'gif']:
            raise HTTPException(status_code=400, detail="Invalid file type. Supported: PDF, PNG, JPEG, WEBP, GIF")

    # 1. Stream file to disk (Memory safe for large files)
    # We use delete=False so we can pass the path to the worker process
    try:
        suffix = f"_{os.path.basename(file.filename)}"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        shutil.copyfileobj(file.file, temp_file)
        temp_path = temp_file.name
        temp_file.close()  # Close handle so worker can open it

        # 2. Offload to Process Pool
        # run_in_executor bridges AsyncIO (FastAPI) and Multiprocessing
        loop = asyncio.get_running_loop()
        
        start_time = time.time()
        logger.info(f"Starting processing for {file.filename}...")
        
        result = await loop.run_in_executor(
            process_pool, 
            core_extraction_logic, 
            temp_path,
            file.filename,
            extractor_type
        )
        
        # DEBUG: Run synchronously to identify errors
        # result = core_extraction_logic(temp_path, file.filename, schema)
        
        duration = time.time() - start_time
        logger.info(f"Finished processing for {file.filename} in {duration:.2f}s")

        # Record metrics
        status = "success"

        return {
            "status": "success",
            "metadata_echo": meta_data,
            "extracted_data": result
        }

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        # Record failure metric
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 3. CRITICAL: Cleanup
        # Ensure file is deleted even if processing crashes
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"Warning: Failed to delete temp file {temp_path}: {e}")




# --- 1. Define Attachment Model ---


class Attachment(BaseModel):
    filename: str
    base64: str  # The base64 encoded string of the file

# --- 2. Define Sub-Request (Request Document) Model ---


class RequestDocument(BaseModel):
    request_document_id: str = Field(..., description="e.g., RQ-69-00103-1")
    activity: str = Field(..., description="e.g., ค่าใช้จ่ายเดินทางอื่นๆในประเทศ")
    amount: float = Field(...)
    paid_by: str = Field(..., description="e.g., employee, to vendor")
    expense_date_or_commit: str = Field(..., description="วันที่ทำเอกสาร")
    attachments: List[Attachment] = Field(default_factory=list)

# --- 3. Define Base Request Model ---


class ClaimSubmitRequest(BaseModel):
    request_id: str = Field(..., description="e.g., RQ-69-00103")
    amount_total: float = Field(...)
    attachments: List[Attachment] = Field(default_factory=list)
    request_documents: List[RequestDocument] = Field(..., description="List of sub requests")


class ClassificationResponse(BaseModel):
    status: str
    message: str
    claim_category: str
    missing_documents: List[str]
    validation_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    extracted_documents: List[Dict[str, Any]]


def core_classification_logic(file_paths: List[str], filenames: List[str], payload: dict = None, model_provider: str = "gemini") -> dict:
    """
    CPU-BOUND BLOCK: This runs in a separate process for classification.
    """
    worker_logger = logging.getLogger("app.worker")

    try:
        file_contents = []
        for file_path in file_paths:
            with open(file_path, "rb") as f:
                file_contents.append(f.read())

        # Call the new unified orchestrator in claim_batch
        final_result = process_claim_batch(file_contents, filenames, payload, model_provider)
        return final_result

    except Exception as e:
        worker_logger.error(f"Classification Error: {e}")
        import traceback
        traceback.print_exc()
        raise e


@app.post("/api/v1/classify_claim", response_model=ClassificationResponse)
async def classify_claim_endpoint(
    payload: ClaimSubmitRequest,
    model_provider: str = "gemini"
):
    loop = asyncio.get_running_loop()
    start_time = time.time()

    temp_paths = []
    filenames = []

    try:
        logger.info(f"Processing Claim: {payload.request_id} with Total Amount: {payload.amount_total}")

        # 1. Process base request attachments (if any)
        for attachment in payload.attachments:
            try:
                # Need to handle potential base64 prefix like 'data:image/png;base64,'
                b64_data = attachment.base64
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]

                file_bytes = base64.b64decode(b64_data)
                suffix = f"_{attachment.filename}"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file.write(file_bytes)
                temp_paths.append(temp_file.name)
                filenames.append(f"{payload.request_id}_{attachment.filename}")
                temp_file.close()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 in root attachment: {attachment.filename}")

        # 2. Process sub-request attachments
        for doc in payload.request_documents:
            logger.info(f"Sub-request: {doc.request_document_id}, Activity: {doc.activity}, Amount: {doc.amount}")
            for doc_attachment in doc.attachments:
                try:
                    b64_data = doc_attachment.base64
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]

                    sub_file_bytes = base64.b64decode(b64_data)
                    suffix = f"_{doc_attachment.filename}"
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    temp_file.write(sub_file_bytes)
                    temp_paths.append(temp_file.name)
                    # Use request_document_id in filename to track it
                    filenames.append(f"{doc.request_document_id}_{doc_attachment.filename}")
                    temp_file.close()
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Invalid base64 in attachment {doc_attachment.filename} of {doc.request_document_id}")

        logger.info(f"Starting batch classification for {len(temp_paths)} files...")

        # 3. Offload to Process Pool
        if temp_paths:
            payload_dict = payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict()
            result = await loop.run_in_executor(
                process_pool, 
                core_classification_logic, 
                temp_paths,
                filenames,
                payload_dict,
                model_provider
            )
        else:
            result = {
                "status": "success",
                "message": "No documents provided.",
                "claim_category": "Unknown",
                "missing_documents": [],
                "extracted_documents": []
            }

        duration = time.time() - start_time
        logger.info(f"Finished batch classification in {duration:.2f}s")

        # Output exactly matches what process_claim_batch returned
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing claim: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 4. Cleanup tmp files
        for path in temp_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {path}: {e}")

if __name__ == "__main__":
    import uvicorn
    # Instrument the app just before running
    # FastAPIInstrumentor.instrument_app(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)