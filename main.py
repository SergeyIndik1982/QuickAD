import os
import httpx
import stripe
import asyncio
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# --- DATABASE SETUP (Railway PostgreSQL) ---
DATABASE_URL = os.getenv("DATABASE_URL") # Railway подставляет это автоматически
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True)
    is_premium = Column(Boolean, default=False)
    credits = Column(Integer, default=3) # Даем 3 бесплатных генерации

Base.metadata.create_all(bind=engine)
# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    # Если мы локально и забыли про БД, используем SQLite, чтобы хотя бы запуститься
    print("⚠️ DATABASE_URL is not set. Falling back to SQLite...")
    DATABASE_URL = "sqlite:///./test.db"
else:
    # Исправляем старый протокол postgres:// на новый postgresql:// для SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
# --- APP SETUP ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ENV
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = STRIPE_SECRET_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- MODELS ---
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

# --- STRIPE LOGIC ---

@app.post("/create-checkout-session")
async def create_checkout_session(data: CheckoutRequest):
    DOMAIN = "https://quickad-production.up.railway.app"
    try:
        # Определяем цену и тип оплаты
        is_subscription = data.plan == "monthly"
        session = stripe.checkout.Session.create(
            mode="subscription" if is_subscription else "payment",
            customer_email=data.email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Cafe Content Pro"},
                    "unit_amount": 1500 if is_subscription else 500,
                    "recurring": {"interval": "month"} if is_subscription else None,
                },
                "quantity": 1,
            }],
            success_url=f"{DOMAIN}/?success=true",
            cancel_url=f"{DOMAIN}/?canceled=true",
        )
        return {"url": session.url}
    except Exception as e:
        return {"error": str(e)}

@app.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db), stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except:
        raise HTTPException(status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["customer_email"]
        
        # Обновляем или создаем пользователя в базе
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, is_premium=True, credits=100)
            db.add(user)
        else:
            user.is_premium = True
            user.credits += 50
        db.commit()
        print(f"✅ User {email} upgraded to Premium")

    return {"status": "ok"}

# --- AI GENERATION LOGIC ---

def build_prompt(data):
    return f"""You are a local barista. Write a natural Instagram caption for {data.cafe_name}. 
    Style: {data.mood}. Goal: {data.goal}. Language: {data.language}.
    Rules: Max 2 lines. No marketing fluff. One ☕ allowed."""

@app.post("/generate")
async def generate(data: GenerateRequest, db: Session = Depends(get_db)):
    # 1. Проверка лимитов
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, is_premium=False, credits=3)
        db.add(user)
        db.commit()
    
    if user.credits <= 0 and not user.is_premium:
        return {"error": "No credits left. Please upgrade."}

    # 2. Генерация через Groq (асинхронно)
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": build_prompt(data)},
                         {"role": "user", "content": "Write it now."}],
            "temperature": 1.0
        }
        
        responses = await asyncio.gather(*[
            client.post(GROQ_URL, headers=headers, json=payload, timeout=10) 
            for _ in range(data.variants)
        ])

        # 3. Списание кредита (если не премиум)
        if not user.is_premium:
            user.credits -= 1
            db.commit()

        results = [res.json()["choices"][0]["message"]["content"].strip() for res in responses if res.status_code == 200]
        return {"texts": results, "remaining_credits": user.credits}

@app.post("/generate-week")
async def generate_week(data: GenerateRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.is_premium:
        raise HTTPException(status_code=403, detail="Upgrade to Premium for weekly plans")

    # Здесь логика генерации на неделю...
    return {"status": "Coming soon for Pro users"}
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
