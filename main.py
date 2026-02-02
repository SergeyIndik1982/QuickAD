import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import openai

# --------------------
# CONFIG
# --------------------
# Make sure your OpenAI key is set as an environment variable in Railway
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

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
# ROUTES
# --------------------
@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    try:
        prompt = SYSTEM_PROMPT + build_user_prompt(
            data.speaker, data.mood, data.occasion, data.variants
        )

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_user_prompt(
                          data.speaker, data.mood, data.occasion, data.variants
                      )}],
            temperature=0.8,
            max_tokens=300
        )

        raw_text = response.choices[0].message.content
        texts = [t.strip() for t in raw_text.split("---") if t.strip()]

    except Exception as e:
        texts = [f"Something went wrong: {e}"]

    return {"texts": texts}
