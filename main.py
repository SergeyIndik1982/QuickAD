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
    target: str
    variants: int = 1
  

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
    # Получаем аудиторию из данных запроса (нужно добавить поле в GenerateRequest)
    target = getattr(data, 'target', 'General') 
    count = data.variants if data.variants > 1 else 1
    
    # Специфические триггеры для каждой группы
    audience_triggers = {
        "Freelancers": "Focus on high-speed Wi-Fi, power outlets, productivity, and the perfect 'flow' state with coffee.",
        "Couples": "Focus on romantic lighting, cozy corners, shared desserts, and intimate conversations.",
        "Coffee Geeks": "Focus on bean origin, roast profiles, brewing methods (V60, Aeropress), and sensory notes.",
        "Families": "Focus on spacious tables, kid-friendly treats, warm service, and a welcoming environment for all ages.",
        "General": "Focus on high-quality service and a welcoming atmosphere."
    }

    trigger = audience_triggers.get(target, audience_triggers["General"])

    # Формируем мощный промпт
    prompt = (
        f"Act as a world-class Social Media Strategist for '{data.cafe_name}'.\n"
        f"Language: {data.language}. Tone: {data.mood}. Focus: {data.goal}.\n"
        f"Target Audience: {target}. {trigger}\n\n"
        f"Task: Write {count} unique Instagram posts. For each post, randomly assign a different 'Time of Day' "
        f"(early morning, golden hour, rainy evening) and 'Weather' to create a dynamic feed.\n\n"
        "STRICT RULES:\n"
        "- Format: [Caption text] | [Detailed Photo script: subject, lighting, angle].\n"
        "- Captions: 2-4 sentences. Competitive, punchy, avoiding clichés like 'Welcome'.\n"
        "- Photo script: Describe a scene that visually tells the story of the caption.\n"
        "- Separator: Use '---' between posts.\n"
        "- Emoji: Max 1-2 per post."
    )
    return prompt
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
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, is_premium=False, credits=3)
        db.add(user); db.commit(); db.refresh(user)
    
    if not user.is_premium and user.credits <= 0:
        return {"error": "credits_depleted"}

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        # Просим AI выдать всё за один раз — это быстрее и надежнее
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "system", "content": build_prompt(data)},
                         {"role": "user", "content": "Generate posts now."}],
            "temperature": 0.8
        }
        
        response = await client.post(GROQ_URL, headers=headers, json=payload, timeout=20)
        
        if response.status_code != 200:
            return {"error": "AI provider error"}

        content = response.json()["choices"][0]["message"]["content"]
        # Разделяем полученный текст на список постов
        results = [text.strip() for text in content.split('---') if text.strip()]

        if results:
            # Списываем 1 кредит за запуск генерации (независимо от кол-ва постов, либо по твоей логике)
            if not user.is_premium:
                user.credits -= 1
                db.commit()
                db.refresh(user)

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
