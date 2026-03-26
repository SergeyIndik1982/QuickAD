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

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ ---
DATABASE_URL = os.getenv("DATABASE_URL")

# Исправление протокола для SQLAlchemy 1.4+
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("⚠️ DATABASE_URL not set. Using SQLite for local development...")
    DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True)
    is_premium = Column(Boolean, default=False)
    credits = Column(Integer, default=3)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# --- 2. НАСТРОЙКА ПРИЛОЖЕНИЯ ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Переменные окружения
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = STRIPE_SECRET_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Dependency для сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 3. МОДЕЛИ Pydantic ---
class GenerateRequest(BaseModel):
    email: str
    cafe_name: str
    language: str
    mood: str
    goal: str
    

class CheckoutRequest(BaseModel):
    email: str
    plan: str

# --- 4. ЛОГИКА ИИ ---
def build_prompt(data: GenerateRequest):
    return f"""
    You are a human barista writing Instagram captions for {data.cafe_name}.
    Style: {data.mood}. Goal: {data.goal}. Language: {data.language}.
    RULES: 1-3 lines max. Natural, no marketing fluff. One ☕ allowed.
    Format your response strictly as: Caption | Photo idea
    """

# --- 5. ЭНДПОИНТЫ ---

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Frontend Error: static/index.html not found</h1>"

@app.post("/generate")
async def generate(data: GenerateRequest, db: Session = Depends(get_db)):
    # Проверка/Создание пользователя
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, is_premium=False, credits=3)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Проверка лимитов
    if not user.is_premium and user.credits <= 0:
        return {"error": "No credits left. Please upgrade to Pro."}

    # Генерация контента
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": build_prompt(data)},
                {"role": "user", "content": f"Write for {data.cafe_name}"}
            ],
            "temperature": 1.0
        }

        # Асинхронные запросы (параллельно)
        tasks = [client.post(GROQ_URL, headers=headers, json=payload, timeout=15) for _ in range(data.variants)]
        responses = await asyncio.gather(*tasks)

        results = []
        for res in responses:
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"].strip()
                if "|" in content:
                    cap, photo = content.split("|", 1)
                    results.append(f"{cap.strip()}\n\n📸 Idea: {photo.strip()}")
                else:
                    results.append(content)

        # Списание кредитов (только если генерация прошла успешно)
        if not user.is_premium and results:
            user.credits -= 1
            db.commit()
            db.refresh(user)

        return {
            "texts": results, 
            "remaining_credits": user.credits, 
            "is_premium": user.is_premium
        }

@app.post("/create-checkout-session")
async def create_checkout_session(data: CheckoutRequest):
    DOMAIN = "https://quickad-production.up.railway.app" # Убедись, что это твой URL
    try:
        is_sub = data.plan == "monthly"
        session = stripe.checkout.Session.create(
            mode="subscription" if is_sub else "payment",
            customer_email=data.email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Cafe Content Pro " + ("Plan" if is_sub else "Credits")},
                    "unit_amount": 1500 if is_sub else 500,
                    "recurring": {"interval": "month"} if is_sub else None,
                },
                "quantity": 1,
            }],
            success_url=f"{DOMAIN}/?success=true",
            cancel_url=f"{DOMAIN}/?canceled=true",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db), stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email")
        
        if email:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(email=email, is_premium=True, credits=100)
                db.add(user)
            else:
                user.is_premium = True
                user.credits += 50
            db.commit()
            print(f"✅ Payment success for: {email}")

    return {"status": "ok"}
