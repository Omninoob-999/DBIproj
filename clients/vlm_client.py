import os
import base64
import logging
import requests
import fitz  # PyMuPDF
from google import genai
from google.genai import types
from ddtrace.llmobs import LLMObs
from openai import AzureOpenAI

logger = logging.getLogger("app.clients.vlm_client")

# Google GenAI Client
gemini_client = None
if os.getenv("GOOGLE_API_KEY"):
    gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Azure OpenAI Client
azure_client = None
if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
    azure_client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-02-01",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )

def _prepare_content_parts(file_content: bytes, filename: str) -> list:
    """Compare content parts from file content (Stage 1 Helper)"""
    content_parts = []
    
    # Handle PDF conversion to image
    if filename.lower().endswith(".pdf"):
        # Open PDF from bytes
        pdf_document = fitz.open(stream=file_content, filetype="pdf")
        
        # Iterate through all pages
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            # Reduce DPI from 150 to 100 or even 72 for large docs
            dpi = 100 if len(pdf_document) < 5 else 72
            pix = page.get_pixmap(dpi=dpi)
            
            img_bytes = pix.tobytes("jpeg", jpg_quality=85)
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            
        pdf_document.close()
    else:
        # Convert to base64
        base64_image = base64.b64encode(file_content).decode('utf-8')
        
        # Determine media type for images
        media_type = "image/jpeg"
        if filename.lower().endswith(".png"):
            media_type = "image/png"
        elif filename.lower().endswith(".gif"):
            media_type = "image/gif"
        elif filename.lower().endswith(".webp"):
            media_type = "image/webp"

        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{base64_image}"
            }
        })
        
    return content_parts

def _call_gemini(system_prompt: str, content_parts: list, prompt_id: str = "gemini-generic") -> str:
    """Call Google Gemini model."""
    if not gemini_client:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
        
    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash-exp") 
    
    parts = []
    for part in content_parts:
        if part["type"] == "text":
            parts.append(types.Part.from_text(text=part["text"]))
        elif part["type"] == "image_url":
            # Extract base64
            data_url = part["image_url"]["url"]
            if "base64," in data_url:
                header, base64_data = data_url.split("base64,")
                # header e.g. "data:image/jpeg;"
                mime_type = header.replace("data:", "").replace(";", "")
                parts.append(types.Part.from_bytes(data=base64.b64decode(base64_data), mime_type=mime_type))
    
    try:
        with LLMObs.annotation_context(prompt={
            "id": prompt_id,
            "template": system_prompt,
            "variables": {"parts_count": len(parts)}
        }):
            response = gemini_client.models.generate_content(
                model=model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=parts
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        raise e

def _call_azure_openai(system_prompt: str, content_parts: list, prompt_id: str = "azure-generic") -> str:
    """Call Azure OpenAI model."""
    if not azure_client:
        raise ValueError("AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not found in .env file")
        
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    
    # Translate content_parts to OpenAI format
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": []}
    ]
    
    for part in content_parts:
        if part["type"] == "text":
            messages[1]["content"].append({"type": "text", "text": part["text"]})
        elif part["type"] == "image_url":
            # For OpenAI we can pass the data URL directly
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": part["image_url"]["url"]
                }
            })
            
    try:
        with LLMObs.annotation_context(prompt={
            "id": prompt_id,
            "template": system_prompt,
            "variables": {"parts_count": len(content_parts)}
        }):
            response = azure_client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Azure OpenAI Error: {e}")
        raise e

def _call_vlm(system_prompt: str, content_parts: list, model_provider: str = "gemini", prompt_id: str = "vlm-generic") -> tuple[str, requests.Response]:
    """Generic VLM Caller (Stage 1 & 3 Helper)"""
    
    response = None
    result_text = ""
    
    if model_provider == "gemini":
        logger.info("Using Gemini model")
        try:
            result_text = _call_gemini(system_prompt, content_parts, prompt_id=prompt_id)
            response = None # No requests response obj for Gemini SDK
        except Exception as e:
            logger.error(f"Gemini invocation failed: {e}")
            raise e
    elif model_provider == "gpt-4o":
        logger.info("Using Azure OpenAI gpt-4o model")
        try:
            result_text = _call_azure_openai(system_prompt, content_parts, prompt_id=prompt_id)
            response = None 
        except Exception as e:
            logger.error(f"Azure OpenAI invocation failed: {e}")
            raise e
    else:
        raise ValueError(f"Unsupported model provider: {model_provider}")

    return result_text, response
