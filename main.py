import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import google.generativeai as genai

# --------------------
# CONFIG
# --------------------
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()
 
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="""
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
)

# --------------------
# HELPERS
# --------------------
def build_user_prompt(speaker, mood, occasion, variants):
    return f"""
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
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

import traceback

@app.post("/generate")
def generate(data: GenerateRequest):
    try:
        prompt = build_user_prompt(
            data.speaker,
            data.mood,
            data.occasion,
            data.variants
        )

        print("PROMPT SENT TO GEMINI:")
        print(prompt)

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 300
            }
        )

        print("RAW RESPONSE:")
        print(response)

        raw_text = response.text
        print("TEXT:")
        print(raw_text)

        texts = [t.strip() for t in raw_text.split("---") if t.strip()]

        return {"texts": texts}

    except Exception as e:
        print("=== GEMINI ERROR ===")
        print(e)
        traceback.print_exc()

        return {
            "texts": ["[ERROR] Check server logs"],
            "error": str(e)
        }

# --------------------
# RUN
# --------------------
# uvicorn main:app --reload
