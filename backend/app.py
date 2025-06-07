import subprocess
import json
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Dict, AsyncGenerator
import difflib
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Keep this for non-stream endpoints, but streaming errors are handled in-stream
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    # If response already started, do nothing
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def detect_changes(old_text: str, new_text: str) -> List[Dict]:
    diff = difflib.Differ().compare(old_text.splitlines(), new_text.splitlines())
    changes, buffer_old, buffer_new = [], [], []
    current_type = None

    def flush():
        nonlocal buffer_old, buffer_new, current_type
        if current_type:
            changes.append({
                'change_type': current_type,
                'old': "\n".join(buffer_old).strip(),
                'new': "\n".join(buffer_new).strip()
            })
            buffer_old, buffer_new, current_type = [], [], None

    for line in diff:
        code, text = line[:2], line[2:]
        if code == '  ':
            flush()
        elif code == '- ':
            current_type = current_type or 'Deleted'
            if current_type == 'Added': current_type = 'Modified'
            buffer_old.append(text)
        elif code == '+ ':
            current_type = current_type or 'Added'
            if current_type == 'Deleted': current_type = 'Modified'
            buffer_new.append(text)
    flush()
    logger.info(f"Detected {len(changes)} change blocks")
    return changes


def analyze_with_llm(change: Dict) -> Dict:
    prompt = (
        "You are a regulatory compliance assistant. Output valid JSON with:\n"
        "1) change_summary: one-sentence summary.\n"
        "2) change_type: one of ['New Requirement','Clarification of Existing Requirement',\n"
        "   'Deletion of Requirement','Minor Edit'].\n"
        "3) potential_impact: brief impact on SOPs.\n\n"
        f"Old Text:\n{change['old']}\n\nNew Text:\n{change['new']}"
    )
    try:
        proc = subprocess.run(
            ['ollama', 'run', 'mistral', prompt],
            check=True,
            capture_output=True,
            text=False,
            timeout=60
        )
        raw = proc.stdout.decode('utf-8', errors='ignore')
    except subprocess.TimeoutExpired:
        logger.error("LLM call timed out")
        raise
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode('utf-8', errors='ignore') if isinstance(e.stderr, bytes) else e.stderr
        logger.error(f"LLM error: {stderr}")
        raise
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM JSON: {raw}")
        raise

async def change_streamer(changes: List[Dict]) -> AsyncGenerator[bytes, None]:
    """
    Yields JSON stream per change, with delays and error handling in-stream.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()
    yield b'{"changes": ['
    first = True
    for change in changes:
        await asyncio.sleep(10)
        try:
            if change['change_type'] in ('Added', 'Modified'):
                details = await loop.run_in_executor(executor, analyze_with_llm, change)
            else:
                details = {
                    'change_summary': 'Section removed',
                    'change_type': 'Deletion of Requirement',
                    'potential_impact': 'Verify removal in SOPs.'
                }
            result = {**change, **details}
        except Exception as e:
            logger.error(f"Error processing change: {e}")
            result = {
                **change,
                'change_summary': 'Error during analysis',
                'change_type': 'Error',
                'potential_impact': str(e)
            }
        chunk = json.dumps(result)
        if not first:
            yield b','
        else:
            first = False
        yield chunk.encode('utf-8')
    yield b']}'
    executor.shutdown(wait=False)

@app.post("/api/analyze")
async def analyze(
    file_v1: UploadFile = File(...),
    file_v2: UploadFile = File(...)
) -> StreamingResponse:
    old_text = (await file_v1.read()).decode('utf-8', errors='ignore')
    new_text = (await file_v2.read()).decode('utf-8', errors='ignore')
    logger.info(f"Received files: {file_v1.filename}, {file_v2.filename}")
    raw_changes = detect_changes(old_text, new_text)
    if not raw_changes:
        return JSONResponse({'changes': []})
    return StreamingResponse(
        change_streamer(raw_changes),
        media_type="application/json"
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
