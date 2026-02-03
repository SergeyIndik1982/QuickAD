import os
import requests
import stripe  # Не забудь добавить в requirements.txt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ключи
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY

URL = "https://api.groq.com/openai/v1/chat/completions"

class GenerateRequest(BaseModel):
    speaker: str
    mood: str
    occasion: str
    variants: int = 3

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# --- НОВЫЙ БЛОК: ОПЛАТА ---
@app.post("/create-checkout-session")
async def create_checkout_session():
    try:
        # Замени на свой реальный домен Railway после деплоя
        YOUR_DOMAIN = "https://quickad-production.up.railway.app" 
        
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': '50 Cafe Credits'},
                    'unit_amount': 500, # $5.00
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{YOUR_DOMAIN}/?success=true",
            cancel_url=f"{YOUR_DOMAIN}/?canceled=true",
        )
        return {"url": checkout_session.url}
    except Exception as e:
        return {"error": str(e)}

# --- ТВОЯ ГЕНЕРАЦИЯ ---
@app.post("/generate")
async def generate(data: GenerateRequest):
    texts = []
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"Context: Cafe. Speaker: {data.speaker}. Mood: {data.mood}. Occasion: {data.occasion}. Write one short, casual, ironic observation. No hashtags, no emojis, no marketing."

    for _ in range(data.variants):
        try:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a witty person writing short cafe notes."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 1.1,
                "max_tokens": 60
            }
            response = requests.post(URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content'].strip()
                texts.append(text)
            else:
                texts.append(f"Groq Error {response.status_code}")
        except Exception as e:
            texts.append("Connection Error")

    return {"texts": texts}