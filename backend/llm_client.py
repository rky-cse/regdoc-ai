import os
import requests
import json
import logging
import time
from typing import Dict

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = "mistral"  # or any other model you loaded via `ollama run`

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def analyze_change_with_llm(text: str, category: str) -> Dict:
    messages = [
        {"role": "system", "content": f"You are an assistant that analyzes code changes for the '{category}' category."},
        {"role": "user", "content": text}
    ]

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False
    }

    logger.debug("Sending to LLM (up to 3 attempts)…")
    content = None

    for attempt in range(1, 4):
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()

            resp_json = resp.json()
            logger.debug("LLM full JSON: %s", json.dumps(resp_json, indent=2)[:500])

            content = resp_json.get("message", {}).get("content", "")

            if content.strip():
                logger.debug("Got non‐empty assistant content on attempt %d", attempt)
                break
            else:
                logger.warning("Empty assistant reply on attempt %d, retrying…", attempt)
        except Exception as e:
            logger.error("LLM HTTP error on attempt %d: %s", attempt, e)
        
        time.sleep(1)

    if not content or not content.strip():
        logger.warning("All attempts yielded empty content; using raw response text")
        content = resp.text

    # Try to parse content as JSON
    try:
        parsed = json.loads(content)
        required = {"change_summary", "change_type", "potential_impact"}
        missing = required - set(parsed)
        if missing:
            raise ValueError(f"Missing keys: {missing}")
        return parsed

    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Invalid JSON from LLM: %s", e, exc_info=True)
        return {"change_summary": "", "change_type": "", "potential_impact": ""}

