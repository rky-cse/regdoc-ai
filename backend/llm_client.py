# llm_client.py

import json
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger("llm_client")

def correct_change_type(change: Dict[str, Any]) -> str:
    old, new = change.get("old", "").strip(), change.get("new", "").strip()
    if not old and new:
        return "Added"
    elif old and not new:
        return "Removed"
    elif old != new:
        return "Modified"
    return "Unchanged"

async def analyze_with_llm(change: Dict[str, Any]) -> Dict[str, str]:
    section = change.get("section")
    old = change.get("old", "")
    new = change.get("new", "")
    corrected_type = correct_change_type(change)

    prompt = (
        "You are a regulatory compliance assistant. Output valid JSON with:\n"
        "1) change_summary: one-sentence summary.\n"
        "2) change_type: one of ['New Requirement','Clarification of Existing Requirement',"
        "'Deletion of Requirement','Minor Edit'].\n"
        "3) potential_impact: brief impact on SOPs.\n\n"
        f"Section.Key: {section}\n"
        f"Change Nature: {corrected_type}\n"
        f"Old Text:\n{old}\n\n"
        f"New Text:\n{new}"
    )

    logger.debug(f"Prompt to LLM:\n{prompt}")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", "http://localhost:11434/api/generate", json={
                "model": "mistral",
                "prompt": prompt,
                "stream": True,
            }) as response:
                chunks = []
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    logger.debug(f"LLM stream chunk: {line}")

                    try:
                        payload = json.loads(line)
                        if payload.get("done"):
                            break
                        if "response" in payload:
                            chunks.append(payload["response"])
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed stream chunk: {line}")

                full_response = ''.join(chunks)
                logger.info(f"LLM completed. Response: {full_response}")

                return json.loads(full_response)

    except Exception as e:
        logger.error(f"LLM error: {e}", exc_info=True)
        return {
            'change_summary': 'Error during analysis',
            'change_type': 'Error',
            'potential_impact': str(e)
        }
