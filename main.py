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
API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
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
    # Промпт для Llama 3
    prompt = f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nContext: Cafe. Speaker: {data.speaker}. Mood: {data.mood}. Write one short casual observation sentence without emojis.<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    texts = []
    
    token = os.getenv("HF_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true"  # Заставляем API подождать загрузки модели
    }

    for _ in range(data.variants):
        try:
            response = requests.post(
                API_URL, 
                headers=headers, 
                json={
                    "inputs": prompt, 
                    "parameters": {
                        "max_new_tokens": 40, 
                        "temperature": 0.6,
                        "top_p": 0.9
                    }
                },
                timeout=30 # Увеличиваем таймаут для Llama
            )
            
            if response.status_code == 200:
                result = response.json()
                # Извлекаем текст
                raw_text = result[0].get("generated_text", "")
                # Убираем промпт, если он вернулся (Llama иногда это делает)
                clean_text = raw_text.split("assistant")[-1].strip() if "assistant" in raw_text else raw_text
                texts.append(clean_text if clean_text else "Just another day.")
            else:
                texts.append(f"Status {response.status_code}: {response.text[:50]}")
                
        except Exception as e:
            texts.append(f"Connection Error: {str(e)[:30]}")

    return {"texts": texts}