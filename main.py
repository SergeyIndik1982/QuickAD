import os
import requests
import stripe
from fastapi import FastAPI, Request, Header, HTTPException
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

# ENV
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

stripe.api_key = STRIPE_SECRET_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# -----------------------
# MODELS
# -----------------------

class GenerateRequest(BaseModel):
    email: str
    cafe_name: str
    language: str
    mood: str
    goal: str
    variants: int = 2

class CheckoutRequest(BaseModel):
    email: str
    plan: str

# -----------------------
# FRONTEND
# -----------------------

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Frontend not found"

# -----------------------
# STRIPE
# -----------------------

@app.post("/create-checkout-session")
async def create_checkout_session(data: CheckoutRequest):
    DOMAIN = "https://quickad-production.up.railway.app"

    try:
        if data.plan == "monthly":
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer_email=data.email,
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Unlimited Cafe Caption"},
                        "unit_amount": 1500,
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }],
                success_url=f"{DOMAIN}/?success=true",
                cancel_url=f"{DOMAIN}/?canceled=true",
            )
        else:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer_email=data.email,
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "50 Credits"},
                        "unit_amount": 500,
                    },
                    "quantity": 1,
                }],
                success_url=f"{DOMAIN}/?success=true",
                cancel_url=f"{DOMAIN}/?canceled=true",
            )

        return {"url": session.url}

    except Exception as e:
        return {"error": str(e)}

# -----------------------
# WEBHOOK
# -----------------------

@app.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except:
        raise HTTPException(status_code=400)

    if event["type"] == "checkout.session.completed":
        print("✅ Payment successful")

    return {"status": "ok"}

# -----------------------
# GENERATE (SHORT + VIRAL)
# -----------------------

def build_prompt(data):
    return f"""
You are a human writing Instagram captions for cafes.

STRICT RULES:
- very short (1–3 lines max)
- natural, imperfect
- no marketing language
- no emojis (except coffee ☕ allowed once)
- no explanations

STYLE:
Tone: {data.mood}
Focus: {data.goal}
Language: {data.language}

Write like a real person.

Output format:
Caption | Photo idea
"""

@app.post("/generate")
async def generate(data: GenerateRequest):
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Запускаем генерацию вариантов параллельно, а не в цикле!
        tasks = []
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": build_prompt(data)},
                {"role": "user", "content": f"Write a caption for {data.cafe_name}"}
            ],
            "temperature": 1.1,
            "max_tokens": 100
        }

        # Выполняем запросы параллельно для скорости
        responses = await asyncio.gather(*[
            client.post(GROQ_URL, headers=headers, json=payload, timeout=10) 
            for _ in range(data.variants)
        ])

        results = []
        for res in responses:
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"].strip()
                # Логика ватермарки
                if "|" in content:
                    cap, photo = content.split("|", 1)
                    results.append(f"{cap.strip()}\n\n☕ Cafe Caption | {photo.strip()}")
                else:
                    results.append(f"{content}\n\n☕ Cafe Caption")
            else:
                results.append("Generation failed")

        return {"texts": results}

# -----------------------
# WEEK GENERATOR (PREMIUM)
# -----------------------

@app.post("/generate-week")
async def generate_week(data: GenerateRequest):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "Create 7 short Instagram captions for a cafe. Format: Day X: Caption | Photo idea. All different, natural."},
                {"role": "user", "content": f"Cafe: {data.cafe_name}, Mood: {data.mood}, Goal: {data.goal}"}
            ],
            "temperature": 1.2,
            "max_tokens": 400
        }
        res = requests.post(GROQ_URL, headers=headers, json=payload)
        
        if res.status_code != 200:
            return {"error": "generation_failed"}
        
        result = res.json()
        content = result["choices"][0]["message"]["content"]
        
        return {"week_content": content}

    except Exception as e:
        return {"error": str(e)}
