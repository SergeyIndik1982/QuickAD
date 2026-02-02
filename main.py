import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from huggingface_hub import InferenceClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Берем токен из переменных Railway
HF_TOKEN = os.getenv("HF_TOKEN")
# Если токена нет, клиент будет работать в анонимном режиме (очень медленно и с ошибками)
client = InferenceClient(token=HF_TOKEN)

class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

def build_prompt(speaker, mood, occasion):
    return f"Cafe observation. Speaker: {speaker}, Mood: {mood}, Context: {occasion}. Short thought:"

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "File static/index.html not found."

@app.post("/generate")
async def generate(data: GenerateRequest):
    prompt = build_prompt(data.speaker, data.mood, data.occasion)
    texts = []

    for _ in range(data.variants):
        try:
            # Используем gpt2 как самую стабильную для проверки
            response = client.text_generation(
                prompt,
                model="gpt2",
                max_new_tokens=40,
                do_sample=True,
                temperature=0.7
            )
            # Убираем промпт из ответа, если он там есть
            result = response.replace(prompt, "").strip()
            texts.append(result if result else "The barista just nodded.")
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: {error_msg}")
            # Если видим 401 — проблема в токене. Если 429 — лимиты.
            texts.append(f"Status: {error_msg[:50]}...") 

    return {"texts": texts}