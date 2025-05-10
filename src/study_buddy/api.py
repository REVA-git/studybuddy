import asyncio
import json
from agency_swarm import AgencyEventHandler
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from study_buddy.main import agency, bubble_bot
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
    complete_response = []  # To store the full response
    # Using a module-level variable would be better for a real application
    # This is just for demo purposes
    global conversation_history
    if not hasattr(router, "conversation_history"):
        router.conversation_history = []

    class StreamEventHandler(AgencyEventHandler):
        @override
        def on_event(self, event: AssistantStreamEvent) -> None:
            # Store chunks if they contain content
            if (
                hasattr(event, "data")
                and hasattr(event.data, "content")
                and event.data.content
            ):
                complete_response.append(event.data.content[0].text.value)
            queue.put(event.model_dump())

        @classmethod
        def on_all_streams_end(cls):
            try:
                # Get the complete assembled response
                last_message = " ".join(complete_response)

                # Update conversation history - in a real app, this would be maintained across requests
                if request.message:
                    router.conversation_history.append(request.message)
                if last_message:
                    router.conversation_history.append(last_message)

                # Limit history to last few messages
                recent_history = (
                    router.conversation_history[-6:]
                    if len(router.conversation_history) > 6
                    else router.conversation_history
                )

                # Generate bubbles using our content-aware implementation
                result = bubble_bot.generate_bubbles(
                    last_study_buddy_message=last_message,
                    conversation_history=recent_history,
                )

                # Add a special event for bubbles
                queue.put(
                    {
                        "type": "bubble_suggestions",
                        "bubbles": result["suggested_bubbles"],
                    }
                )
            except Exception as e:
                # If bubble generation fails, log error but don't block the response
                queue.put({"type": "bubble_error", "error": str(e)})
            finally:
                # Mark the stream as done
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
