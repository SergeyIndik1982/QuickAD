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
    weather: str = "Random"
    time: str = "Random"
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
    # Достаем параметры, если их нет — ставим дефолт
    target = getattr(data, 'target', 'General')
    count = data.variants if data.variants > 1 else 1
    
    # Словарь триггеров: это "контекстное топливо" для AI
    audience_triggers = {
        "Freelancers": "Focus on productivity, deep work flow, high-speed Wi-Fi, and the 'third place' vibe between home and office.",
        "Couples": "Focus on intimacy, soft lighting, shared moments, 'analog' connection, and cozy aesthetic.",
        "Coffee Geeks": "Focus on extraction science, bean processing, flavor notes (acidity, body), and brewing precision.",
        "Families": "Focus on mental break for parents, safe space for kids, morning rituals, and easy-going energy.",
        "General": "Focus on high-quality hospitality and urban sanctuary vibes."
    }

    trigger = audience_triggers.get(target, audience_triggers["General"])
    
    # Логика окружения (погода и время)
    weather_ctx = f"Weather: {data.weather}." if data.weather != "Random" else "Weather: Surprise me (match it to the caption mood)."
    time_ctx = f"Time of Day: {data.time}." if data.time != "Random" else "Time of Day: Surprise me (vary it for different posts)."

    # ФОРМИРУЕМ ИНСТРУКЦИЮ (Prompt Engineering)
    prompt = (
        f"Context: You are the Voice of Brand for '{data.cafe_name}'. "
        f"Language: {data.language}. Tone: {data.mood}. Target: {target}.\n"
        f"Constraints: {trigger} {weather_ctx} {time_ctx}\n\n"
        
        f"Task: Write {count} Instagram posts that follow this High-Conversion structure:\n"
        "1. Hook: Start with a punchy, relatable observation (max 1 sentence).\n"
        "2. Body: Use the PAS framework (Problem: bad mood/need for focus -> Agitation: urban noise/rainy day -> Solution: your cafe).\n"
        "3. CTA: A subtle, non-pushy invitation.\n\n"
        
        "Formatting Rules:\n"
        "- Format: [Caption] | [Photo Script]\n"
        "- Photo Script: Be specific. Describe lighting (cinematic, warm, moody), props, and camera angle (flat lay, close-up).\n"
        "- Separator: '---'\n"
        "- Language: Strict {data.language}. No English words unless it's coffee terminology.\n"
        "- Emojis: Max 2 per post, placed naturally."
    )
    return prompt
# --- ENDPOINTS ---

@app.get("/get-credits")
def get_credits(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, credits=3, is_premium=False)
        db.add(user); db.commit(); db.refresh(user)
    return {"credits": user.credits, "is_premium": user.is_premium}


@app.post("/generate")
async def generate(data: GenerateRequest, db: Session = Depends(get_db)):
    # Список email-адресов, для которых всё бесплатно и бесконечно
    ADMIN_EMAILS = ["indikautor@gmail.com"] 

    user = db.query(User).filter(User.email == data.email).first()
    
    # Если ты админ — создаем или обновляем запись с бесконечными кредитами
    if data.email in ADMIN_EMAILS:
        if not user:
            user = User(email=data.email, is_premium=True, credits=999)
            db.add(user); db.commit(); db.refresh(user)
        else:
            user.is_premium = True # Делаем админа премиумом навсегда
            db.commit()
    
    # Стандартная проверка для обычных пользователей
    if not user:
        user = User(email=data.email, is_premium=False, credits=3)
        db.add(user); db.commit(); db.refresh(user)
    
    if not user.is_premium and user.credits <= 0:
        return {"error": "credits_depleted"}

    # Дальше идет сам вызов AI (async with httpx.AsyncClient()...)
    # ...
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": build_prompt(data)},
                {"role": "user", "content": "Generate content now."}
            ],
            "temperature": 0.8
        }
        
        try:
            response = await client.post(GROQ_URL, headers=headers, json=payload, timeout=30)
            if response.status_code != 200:
                return {"error": f"Groq Error: {response.text}"}
            
            content = response.json()["choices"][0]["message"]["content"]
            results = [text.strip() for text in content.split('---') if text.strip()]

            if results:
                if not user.is_premium:
                    user.credits -= 1
                    db.commit()
                return {"texts": results, "remaining_credits": user.credits}
            
            return {"error": "Failed to parse AI response"}
        except Exception as e:
            return {"error": str(e)}

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
