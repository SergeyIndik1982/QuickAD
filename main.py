import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from huggingface_hub import InferenceClient

# --------------------
# INIT APP
# --------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Используем API вместо локальной модели
# Если хочешь результат покачественнее, замени "distilgpt2" на "mistralai/Mistral-7B-v0.1"
HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient("distilgpt2", token=HF_TOKEN)

# --------------------
# SCHEMA & HELPERS (оставляем как было)
# --------------------
class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

def build_prompt(speaker, mood, occasion):
    # Добавим явный маркер конца для API
    return f"""Context:
Speaker: {speaker}
Mood: {mood}
Occasion: {occasion}

Task: Write a short, casual, slightly ironic observation about a cafe. 
No marketing, no emojis, no exclamation marks.
Note:"""

# --------------------
# ROUTES
# --------------------
@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Static file not found. Check folder structure."

@app.post("/generate")
async def generate(data: GenerateRequest):
    prompt = build_prompt(data.speaker, data.mood, data.occasion)
    texts = []
    
    # gpt2 — самая быстрая и безотказная для тестов
    model_id = "gpt2" 

    for _ in range(data.variants):
        try:
            # Убрали wait_for_model, так как он вызвал ошибку
            response = client.text_generation(
                prompt,
                model=model_id,
                max_new_tokens=50,
                do_sample=True,
                temperature=0.8,
            )
            texts.append(response.strip())
        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
            texts.append("The barista is cleaning the counter. Try again.")

    return {"texts": texts}