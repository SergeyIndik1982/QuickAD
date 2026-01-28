from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

# =====================
# AI CONFIG (SAFE)
# =====================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

model = None
model_error = None

if GOOGLE_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        model_error = str(e)
else:
    model_error = "GOOGLE_API_KEY not set"

# =====================
# APP
# =====================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# STATIC FRONTEND
# =====================
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# =====================
# SCHEMA
# =====================
class GenerateRequest(BaseModel):
    business_type: str
    tone: str
    platform: str

# =====================
# API
# =====================
@app.post("/generate")
def generate(req: GenerateRequest):
    if not model:
        raise HTTPException(status_code=500, detail=model_error)

    prompt = (
        f"Write a short {req.platform} marketing post.\n\n"
        f"Business: {req.business_type}\n"
        f"Tone: {req.tone}\n\n"
        f"Use emojis. Plain text only."
    )

    response = model.generate_content(prompt)
    return {"post": response.text}
