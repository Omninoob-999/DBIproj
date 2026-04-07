import json

def _parse_json_result(result_text: str) -> dict:
    """Helper to safely parse JSON strings returned by LLMs."""
    # Clean up markdown code blocks
    if result_text.strip().startswith("```"):
        result_text = result_text.strip().split("\n", 1)[-1]
        if result_text.strip().endswith("```"):
            result_text = result_text.strip().rsplit("\n", 1)[0]
            
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        # Retry with substring search
        start = result_text.find("{")
        end = result_text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(result_text[start:end+1])
            except:
                pass
        raise Exception("Failed to parse JSON response: " + result_text[:100] + "...")
