from agency_swarm import AgencyEventHandler
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from teaching_assistant.main import agency
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


from typing_extensions import override
from agency_swarm import AgencyEventHandler


class EventHandler(AgencyEventHandler):
    @override
    def on_text_created(self, text) -> None:
        # Get the name of the agent that is sending the message
        print(
            f"\n{self.recipient_agent_name} @ {self.agent_name}  > ", end="", flush=True
        )

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)

    def on_tool_call_created(self, tool_call):
        print(f"\n{self.recipient_agent_name} > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == "code_interpreter":
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

    @classmethod
    def on_all_streams_end(cls):
        print(
            "\n\nAll streams have ended."
        )  # Conversation is over and message is returned to the user.


def stream_response(message):
    return StreamingResponse(
        agency.get_completion(message, yield_messages=True),
        media_type="text/event-stream",
    )


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):

    return StreamingResponse(
        agency.get_completion_stream(request.message, EventHandler),
        media_type="text/event-stream",
    )
