import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
import traceback

# --------------------
# CONFIG
# --------------------

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
app = FastAPI()

SYSTEM_PROMPT = """
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
"""

# --------------------
# HELPERS
# --------------------

def build_prompt(speaker, mood, occasion, variants):
    return f"""{SYSTEM_PROMPT}

Who is speaking: {speaker}
Mood: {mood}
Occasion: {occasion}

Generate {variants} short texts.
Each text:
- 2–4 lines
- separated by ---
- unfinished
"""

# --------------------
# SCHEMA
# --------------------

class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

# --------------------
# ROUTES
# --------------------

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    try:
        prompt = build_prompt(
            data.speaker,
            data.mood,
            data.occasion,
            data.variants
        )

        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents=prompt,
            config={
                "temperature": 0.8,
                "max_output_tokens": 300,
            }
        )

        raw = response.text or ""
        texts = [t.strip() for t in raw.split("---") if t.strip()]

        return {"texts": texts}

    except Exception as e:
        print("=== GEMINI ERROR ===")
        print(e)
        traceback.print_exc()
        return {"texts": ["[ERROR] Check server logs"]}

# --------------------
# RUN
# --------------------
# uvicorn main:app --reload
