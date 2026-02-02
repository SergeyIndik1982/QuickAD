import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

# --------------------
# CONFIG
# --------------------
openai.api_key = os.getenv("OPENAI_API_KEY")  # Railway environment variable

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------
# SCHEMA
# --------------------
class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

# --------------------
# HELPERS
# --------------------
def build_prompt(speaker, mood, occasion, variants):
    return f"""
Generate {variants} short unfinished texts.

Context:
Speaker: {speaker}
Mood: {mood}
Occasion: {occasion}

Rules:
- calm
- simple
- slightly ironic at times
- never promotional
- 2–4 lines each
- unfinished
- separate each text by ---
Forbidden:
- calls to action
- exclamation marks
- emojis
- marketing language
- positive conclusions
Do not explain. Do not conclude. If unsure, write less.
"""

# --------------------
# ROUTES
# --------------------
@app.get("/")
def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    prompt = build_prompt(data.speaker, data.mood, data.occasion, data.variants)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=300
        )
        text = response.choices[0].message.content
        texts = [t.strip() for t in text.split("---") if t.strip()]
    except Exception as e:
        print(e)
        texts = ["Something went wrong."]
    return {"texts": texts}
