from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a test assistant. Be extremely concise. If a question has options, respond with only the correct option (e.g. 'B' or 'B) option text'). For numerical questions, give only the value with units if needed. For short-answer questions, give the briefest correct answer. No explanations, no working, no commentary.",
}


class ChatRequest(BaseModel):
    messages: list[dict]


@app.post("/api/chat")
async def chat(request: ChatRequest):
    messages = [SYSTEM_PROMPT] + request.messages[-20:]
    try:
        response = client.chat.completions.create(
            model="gpt-5.4",
            messages=messages,
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
