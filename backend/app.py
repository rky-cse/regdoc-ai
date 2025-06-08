import json
import logging
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Dict, Any, AsyncGenerator
import asyncio
from concurrent.futures import ThreadPoolExecutor

from langchain_community.llms import Ollama
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

from diff_utils import detect_paragraph_section_changes as detect_changes  # now returns List[Dict]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
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
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# LangChain setup
llm = Ollama(model="mistral")
memory = ConversationBufferMemory()
conversation = ConversationChain(llm=llm, memory=memory)


def analyze_with_llm(change: Dict[str, Any]) -> Dict[str, str]:
    """
    Sends a prompt about the single change to the LLM, expects JSON with
    change_summary, change_type, potential_impact.
    """
    prompt = (
        "You are a regulatory compliance assistant. Output valid JSON with:\n"
        "1) change_summary: one-sentence summary.\n"
        "2) change_type: one of ['New Requirement','Clarification of Existing Requirement',"
        "'Deletion of Requirement','Minor Edit'].\n"
        "3) potential_impact: brief impact on SOPs.\n\n"
        f"Section.Key: {change.get('section')}\n"
        f"Old Text:\n{change.get('old')}\n\n"
        f"New Text:\n{change.get('new')}"
    )
    try:
        raw = conversation.run(prompt)
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response: {raw}")
        raise
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise


async def change_streamer(changes: List[Dict[str, Any]]) -> AsyncGenerator[bytes, None]:
    """
    Streams out a JSON array, calling the LLM on Added/Modified changes.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    yield b'{"changes":['
    first = True

    for change in changes:
        # small delay for demonstration; adjust or remove as needed
        await asyncio.sleep(0.1)

        if change['change_type'] in ('Added', 'Modified'):
            try:
                details = await loop.run_in_executor(executor, analyze_with_llm, change)
            except Exception as e:
                details = {
                    'change_summary': 'Error during analysis',
                    'change_type': 'Error',
                    'potential_impact': str(e)
                }
        else:
            # For "Removed"
            details = {
                'change_summary': 'Section removed',
                'change_type': 'Deletion of Requirement',
                'potential_impact': 'Verify removal in SOPs.'
            }

        result = {**change, **details}

        if not first:
            yield b','
        first = False
        yield json.dumps(result).encode('utf-8')

    yield b']}'  # close JSON
    executor.shutdown(wait=False)


@app.post("/api/analyze")
async def analyze(
    file_v1: UploadFile = File(...),
    file_v2: UploadFile = File(...)
) -> StreamingResponse:
    old_text = (await file_v1.read()).decode('utf-8', errors='ignore')
    new_text = (await file_v2.read()).decode('utf-8', errors='ignore')
    logger.info(f"Received files: {file_v1.filename}, {file_v2.filename}")

    # detect_changes now returns a flat List[Dict[str, old, new, section, change_type]]
    changes = detect_changes(old_text, new_text)

    if not changes:
        return JSONResponse({'changes': []})

    return StreamingResponse(
        change_streamer(changes),
        media_type="application/json"
    )


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
