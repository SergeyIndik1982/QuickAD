import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
URL = "https://api.groq.com/openai/v1/chat/completions"

class GenerateRequest(BaseModel):
    situation: str

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
async def generate(data: GenerateRequest):

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
You are writing a natural Instagram caption for a real café.

This is not marketing.
Do not sell anything.
No calls to action.
No exclamation marks.
No emojis.
No promotional tone.

Write as if someone inside the café typed this quickly between tasks.

The caption may feel slightly unfinished.
It does not need a conclusion.
Some sentences can be very short.
Vary sentence length naturally.

Include exactly one small, subtle real-life detail
(a sound, light, movement, minor mistake, tiny observation).
Do not over-describe the detail. Keep it casual.

Avoid poetic language.
Avoid dramatic tone.
Avoid metaphors.
Avoid storytelling structure.
Avoid inspirational phrasing.
Avoid marketing adjectives.
Avoid announcements.

Do not start every caption the same way.
Do not use obvious openers like “Another day”, “Today”, “There’s something about”.

Let the tone feel slightly imperfect, mildly tired, or casually distracted if it fits the situation.

Keep it understated.
Keep it human.
Keep it real.

Situation: {data.situation}

Length: 2–5 short paragraphs.

Write only the caption text.
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.1,
        "max_tokens": 180
    }

    try:
        response = requests.post(URL, headers=headers, json=payload, timeout=15)
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        return {"text": text}

    except Exception:
        return {"text": "Generation error"}
