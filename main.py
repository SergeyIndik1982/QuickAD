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
API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-3.2-1B-Instruct"
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
    # Промпт для новой Llama 3.2
    prompt = f"User: Write a short, casual, ironic cafe observation from a {data.speaker} in a {data.mood} mood. No emojis. One sentence.\nAssistant:"
    
    token = os.getenv("HF_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    texts = []
    for _ in range(data.variants):
        try:
            # Hugging Face теперь требует передавать параметры внутри 'parameters'
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 50,
                    "temperature": 0.7,
                    "return_full_text": False
                },
                "options": {
                    "wait_for_model": True # Теперь это передается в 'options'
                }
            }

            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                # Обработка ответа (может быть списком или словарем)
                text = result[0].get("generated_text", "") if isinstance(result, list) else result.get("generated_text", "")
                texts.append(text.strip() if text else "Silence in the cafe.")
            else:
                # Если опять 410 или 404 — выводим ПОЛНЫЙ текст ошибки от HF
                error_info = response.json().get("error", response.text)
                texts.append(f"API Error ({response.status_code}): {error_info[:50]}")
                
        except Exception as e:
            texts.append(f"System Error: {str(e)[:30]}")

    return {"texts": texts}