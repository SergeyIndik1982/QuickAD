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

HF_TOKEN = os.getenv("HF_TOKEN")
# Используем GPT-2 как самую быструю
API_URL = "https://api-inference.huggingface.co/models/openai-community/gpt2"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

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
    prompt = f"Note: {data.speaker}. Mood: {data.mood}. Thought:"
    texts = []

    for _ in range(data.variants):
        try:
            # 1. Проверяем токен прямо перед отправкой
            token = os.getenv("HF_TOKEN")
            if not token:
                texts.append("Error: HF_TOKEN variable is missing in Railway!")
                continue

            response = requests.post(
                API_URL, 
                headers={"Authorization": f"Bearer {token.strip()}"}, # Чистим от пробелов
                json={"inputs": prompt, "parameters": {"max_new_tokens": 30}},
                timeout=15
            )
            
            # 2. Логируем статус
            if response.status_code == 200:
                result = response.json()
                gen_text = result[0]["generated_text"].replace(prompt, "").strip()
                texts.append(gen_text if gen_text else "The cafe is empty.")
            else:
                # ВЫВОДИМ КОД ОШИБКИ (401, 404, 503)
                texts.append(f"Server Error Code: {response.status_code}")
                
        except Exception as e:
            texts.append(f"Local Error: {str(e)[:30]}")

    return {"texts": texts}