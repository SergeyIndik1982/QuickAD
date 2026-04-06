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

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True)
    is_premium = Column(Boolean, default=False)
    credits = Column(Integer, default=3)

Base.metadata.create_all(bind=engine)

# --- APP SETUP ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = STRIPE_SECRET_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- MODELS & UTILS ---
class GenerateRequest(BaseModel):
    email: str
    cafe_name: str
    language: str
    mood: str
    goal: str
  

class CheckoutRequest(BaseModel):
    email: str
    plan: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def build_prompt(data):
    return (f"Write 1 Instagram caption for a cafe named '{data.cafe_name}'. "
            f"Language: {data.language}. Style: {data.mood}. Focus: {data.goal}. "
            "Format: [Caption text] | [Photo idea]. Short, organic, max 1 emoji. "
            "Example: Freshly brewed peace. | A close-up of steam rising from a ceramic mug.")

# --- ENDPOINTS ---

@app.get("/get-credits")
def get_credits(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, credits=3, is_premium=False)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"credits": user.credits, "is_premium": user.is_premium}

@app.post("/generate")
async def generate(data: GenerateRequest, db: Session = Depends(get_db)):
    # 1. Проверка юзера
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, is_premium=False, credits=3)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # 2. Лимиты
    if not user.is_premium and user.credits <= 0:
        return {"error": "No credits left. Please upgrade."}

    # 3. Запрос к AI
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": build_prompt(data)},
                         {"role": "user", "content": "Generate now."}],
            "temperature": 0.8
        }
        
        responses = await asyncio.gather(*[
            client.post(GROQ_URL, headers=headers, json=payload, timeout=15) 
            for _ in range(data.variants)
        ])

        # 4. Списание кредитов
        if not user.is_premium:
            user.credits -= 1
            db.commit()

        results = [res.json()["choices"][0]["message"]["content"].strip() for res in responses if res.status_code == 200]
        return {"texts": results, "remaining_credits": user.credits}

@app.post("/create-checkout-session")
async def create_checkout_session(data: CheckoutRequest):
    DOMAIN = "https://quickad-production.up.railway.app"
    try:
        session = stripe.checkout.Session.create(
            mode="subscription" if data.plan == "monthly" else "payment",
            customer_email=data.email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Cafe Content Pro"},
                    "unit_amount": 1500 if data.plan == "monthly" else 500,
                    "recurring": {"interval": "month"} if data.plan == "monthly" else None,
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
        email = session.get("customer_email")
        if email:
            user = db.query(User).filter(User.email == email).first()
            if user:
                user.is_premium = True
                user.credits += 50
                db.commit()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Frontend file not found in /static folder"
