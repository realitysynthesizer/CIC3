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
    "content": "You are a helpful tutor. Answer assignment questions clearly and thoroughly. When shown images of questions, read them carefully and provide complete answers.",
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
