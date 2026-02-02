import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai

# --------------------
# CONFIG
# --------------------
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])  # Railway environment variable

app = FastAPI()

# --------------------
# SYSTEM PROMPT
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

# --------------------
# HELPERS
# --------------------
def build_user_prompt(speaker, mood, occasion, variants):
    return f"""
{SYSTEM_PROMPT}

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
    # Serve your static HTML
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=build_user_prompt(
                data.speaker,
                data.mood,
                data.occasion,
                data.variants
            ),
            temperature=0.8,
            max_output_tokens=300
        )
        raw = response.text or ""
        texts = [t.strip() for t in raw.split("---") if t.strip()]
    except Exception:
        texts = ["Something went wrong."]
    return {"texts": texts}

# --------------------
# RUN (optional for local)
# --------------------
# uvicorn main:app --reload
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai

# --------------------
# CONFIG
# --------------------
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])  # Railway environment variable

app = FastAPI()

# --------------------
# SYSTEM PROMPT
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

# --------------------
# HELPERS
# --------------------
def build_user_prompt(speaker, mood, occasion, variants):
    return f"""
{SYSTEM_PROMPT}

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
    # Serve your static HTML
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate")
def generate(data: GenerateRequest):
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=build_user_prompt(
                data.speaker,
                data.mood,
                data.occasion,
                data.variants
            ),
            temperature=0.8,
            max_output_tokens=300
        )
        raw = response.text or ""
        texts = [t.strip() for t in raw.split("---") if t.strip()]
    except Exception:
        texts = ["Something went wrong."]
    return {"texts": texts}

# --------------------
# RUN (optional for local)
# --------------------
# uvicorn main:app --reload
