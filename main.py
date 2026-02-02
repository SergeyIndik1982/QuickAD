import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import pipeline, set_seed

# --------------------
# CONFIG
# --------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Hugging Face generator
generator = pipeline("text-generation", model="distilgpt2")
set_seed(42)  # For reproducible results

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
@app.get("/")
def root():
    return {"status": "QuickAD alive"}

@app.post("/generate")
def generate(data: GenerateRequest):
    prompt = build_prompt(data.speaker, data.mood, data.occasion)
    texts = []
    
    for _ in range(data.variants):
        result = generator(prompt, max_length=50, num_return_sequences=1)
        text = result[0]['generated_text'].replace(prompt, '').strip()
        texts.append(text)
    
    return {"texts": texts}
