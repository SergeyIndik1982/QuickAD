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
API_URL = "https://api-inference.huggingface.co/models/gpt2"
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
    prompt = f"Note: {data.speaker} is feeling {data.mood} because of {data.occasion}. Observation:"
    texts = []

    for _ in range(data.variants):
        try:
            # Прямой POST запрос к API
            response = requests.post(
                API_URL, 
                headers=HEADERS, 
                json={"inputs": prompt, "parameters": {"max_new_tokens": 30, "do_sample": True}},
                timeout=10
            )
            
            result = response.json()
            
            # Обработка разных ответов API
            if isinstance(result, list) and "generated_text" in result[0]:
                gen_text = result[0]["generated_text"].replace(prompt, "").strip()
                texts.append(gen_text if gen_text else "A quiet moment in the cafe.")
            elif "error" in result:
                texts.append(f"API Error: {result['error'][:40]}")
            else:
                texts.append("The barista is silent.")
                
        except Exception as e:
            texts.append(f"Connection error: {str(e)[:30]}")

    return {"texts": texts}