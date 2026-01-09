from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import os
from dotenv import load_dotenv

# load env
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI()

# CORS (чтобы HTML работал)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    business_type: str
    tone: str
    platform: str

@app.post("/generate")
async def generate(req: GenerateRequest):
    prompt = f"""
You are a marketing copywriter.

Create a short {req.platform} post for a {req.business_type}.
Tone: {req.tone}.
Use emojis and hashtags.
"""

    try:
        response = model.generate_content(prompt)

        return {
            "text": response.text
        }

    except Exception as e:
        return {
            "error": str(e)
        }
