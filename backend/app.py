import json
import logging
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Dict, Any, AsyncGenerator
import asyncio
import httpx

from llm_client import analyze_with_llm, correct_change_type

from diff_utils import detect_paragraph_section_changes as detect_changes

# ───── Logging Setup ─────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

async def change_streamer(changes: List[Dict[str, Any]]) -> AsyncGenerator[bytes, None]:
    logger.info(f"Streaming {len(changes)} changes")
    yield b'{"changes":['
    first = True

    for idx, change in enumerate(changes):
        logger.debug(f"Processing change #{idx + 1}: {change}")

        change['change_type'] = correct_change_type(change)

        await asyncio.sleep(0.1)  # Optional delay for UX

        if change['change_type'] in ('Added', 'Modified'):
            details = await analyze_with_llm(change)
        elif change['change_type'] == 'Removed':
            details = {
                'change_summary': 'Section removed',
                'change_type': 'Deletion of Requirement',
                'potential_impact': 'Verify removal in SOPs.'
            }
        else:
            details = {
                'change_summary': 'No significant change detected',
                'change_type': 'Minor Edit',
                'potential_impact': 'Negligible'
            }

        result = {**change, **details}
        logger.debug(f"Final result: {result}")

        if not first:
            yield b','

        yield json.dumps(result).encode('utf-8')
        first = False

    yield b']}'


@app.post("/api/analyze")
async def analyze(
    file_v1: UploadFile = File(...),
    file_v2: UploadFile = File(...)
) -> StreamingResponse:
    logger.info(f"Received files: {file_v1.filename}, {file_v2.filename}")

    old_text = (await file_v1.read()).decode('utf-8', errors='ignore')
    new_text = (await file_v2.read()).decode('utf-8', errors='ignore')

    logger.debug("Calling diff detector...")
    changes = detect_changes(old_text, new_text)
    logger.info(f"Total changes detected: {len(changes)}")

    if not changes:
        logger.info("No changes found.")
        return JSONResponse({'changes': []})

    return StreamingResponse(
        change_streamer(changes),
        media_type="application/json"
    )


if __name__ == '__main__':
    import uvicorn
    logger.info("Starting FastAPI app on http://localhost:8000")
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
