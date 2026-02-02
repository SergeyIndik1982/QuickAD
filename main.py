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

# Используем Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
URL = "https://api.groq.com/openai/v1/chat/completions"

class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
async def generate(data: GenerateRequest):
    texts = []
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Промпт для качественной модели Llama-3
    prompt = f"Context: Cafe. Speaker: {data.speaker}. Mood: {data.mood}. Occasion: {data.occasion}. Write one short, casual, ironic observation. No hashtags, no emojis, no marketing."

    for _ in range(data.variants):
        try:
            payload = {
                "model": "llama-3.3-70b-versatile", # Мощная и быстрая модель
                "messages": [
                    {"role": "system", "content": "You are a witty person writing short cafe notes."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 1.1,
                "max_tokens": 60
            }

            response = requests.post(URL, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content'].strip()
                texts.append(text)
            else:
                texts.append(f"Groq Error {response.status_code}: {response.text[:50]}")
                
        except Exception as e:
            texts.append(f"Connection Error: {str(e)[:30]}")

    return {"texts": texts}