import asyncio
import json
from agency_swarm import AgencyEventHandler
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from study_buddy.main import agency
from queue import Queue, Empty
import threading
from openai.types.beta import AssistantStreamEvent

from study_buddy.models.request_models import AgencyRequestStreaming

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


from typing_extensions import override
from agency_swarm import AgencyEventHandler


@router.post("/chat")
async def get_completion_stream(request: AgencyRequestStreaming):
    queue = Queue()

    class StreamEventHandler(AgencyEventHandler):
        @override
        def on_event(self, event: AssistantStreamEvent) -> None:
            queue.put(event.model_dump())

        @classmethod
        def on_all_streams_end(cls):
            queue.put("[DONE]")

        @classmethod
        def on_exception(cls, exception: Exception):
            # Store the actual exception
            queue.put({"error": str(exception)})

    async def generate_response():
        try:

            def run_completion():
                try:
                    agency.get_completion_stream(
                        request.message,
                        message_files=request.message_files,
                        recipient_agent=request.recipient_agent,
                        additional_instructions=request.additional_instructions,
                        attachments=request.attachments,
                        tool_choice=request.tool_choice,
                        response_format=request.response_format,
                        event_handler=StreamEventHandler,
                    )
                except Exception as e:
                    # Send the actual exception
                    queue.put({"error": str(e)})

            thread = threading.Thread(target=run_completion)
            thread.start()

            while True:
                try:
                    event = await asyncio.to_thread(queue.get, timeout=30)
                    if event == "[DONE]":
                        break
                    # If it's an error event
                    if isinstance(event, dict) and "error" in event:
                        yield f"data: {json.dumps(event)}\n\n"
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
