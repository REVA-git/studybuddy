from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from teaching_assistant.main import agency

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    response = agency.get_completion(request.message)

    return StreamingResponse(response, media_type="text/plain")
