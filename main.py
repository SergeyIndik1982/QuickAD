from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from transformers import pipeline

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

# --------------------
# INIT FREE MODEL
# --------------------
text_generator = pipeline("text-generation", model="distilgpt2")

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
def build_prompt(speaker, mood, occasion):
    return f"""
You are a real person connected to a cafe.
You are NOT a marketer and NOT writing ads.

Write short, casual observations.
They may feel unfinished.

Rules:
- calm
- simple
- slightly ironic at times
- never promotional

Forbidden:
- calls to action
- exclamation marks
- emojis
- marketing language
- positive conclusions

Do not explain.
Do not conclude.
If unsure, write less.

Context:
Speaker: {speaker}
Mood: {mood}
Occasion: {occasion}
"""

# --------------------
# ROUTES
# --------------------
@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    prompt = build_prompt(data.speaker, data.mood, data.occasion)
    texts = []

    for _ in range(data.variants):
        try:
            output = text_generator(
                prompt,
                max_length=100,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
            )
            text = output[0]["generated_text"].replace(prompt, "").strip()
            # Разделяем на 2-4 строчки, как в оригинальном промте
            text_lines = text.split("\n")
            texts.append("\n".join(text_lines[:4]))
        except Exception as e:
            texts.append("Something went wrong.")

    return {"texts": texts}
