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
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
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
    prompt = f"Context: Cafe. Speaker: {data.speaker}. Mood: {data.mood}. Write one short, casual sentence of observation:"
    texts = []
    
    token = os.getenv("HF_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(data.variants):
        try:
            response = requests.post(
                API_URL, 
                headers=headers, 
                json={
                    "inputs": prompt, 
                    "parameters": {"max_new_tokens": 50, "return_full_text": False}
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                # Обработка ответа от Mistral
                if isinstance(result, list):
                    text = result[0].get("generated_text", "").strip()
                else:
                    text = result.get("generated_text", "").strip()
                texts.append(text if text else "The cup is empty.")
            
            elif response.status_code == 503:
                # Это ХОРОШИЙ знак, значит модель просто грузится
                texts.append("Barista is waking up... Click again in 15 seconds.")
            
            else:
                # Если опять будет ошибка, мы увидим её ПОЛНОСТЬЮ
                texts.append(f"Status {response.status_code}: {response.json().get('error', 'Unknown error')}")
                
        except Exception as e:
            texts.append(f"Local Error: {str(e)[:30]}")

    return {"texts": texts}