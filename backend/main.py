from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
import os

app = FastAPI()

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # можно сузить
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Static frontend =====
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# ===== OpenRouter config =====
API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_KEY_HERE")
API_URL = "https://openrouter.ai/api/v1/responses"
MODEL = "anthropic/claude-3.5-sonnet"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ===== API endpoint =====
@app.post("/generate")
async def generate_post(req: Request):
    data = await req.json()
    prompt = f"Write a {data.get('tone')} post for {data.get('platform')} for a {data.get('business_type')}."

    payload = {"model": MODEL, "input": prompt, "max_output_tokens": 300}

    try:
        res = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
        res.raise_for_status()
        resp = res.json()

        # Попробуем достать текст
        text = resp.get("output_text")
        if not text and "output" in resp:
            try:
                text = resp["output"][0]["content"][0]["text"]
            except Exception:
                text = None

        return JSONResponse({"text": text or "Error: no output from API"})

    except requests.exceptions.RequestException as e:
        return JSONResponse({"text": f"Error: {e}"})
