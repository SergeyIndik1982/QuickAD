import os
import httpx
import stripe
import asyncio
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    target: str = "General"
    weather: str = "Random"
    time: str = "Random"
    event: str = ""  # Добавили значение по умолчанию (пустая строка)
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
    target = getattr(data, 'target', 'General')
    event = getattr(data, 'event', '') 
    count = data.variants if data.variants > 0 else 1
    
    audience_triggers = {
        "Freelancers": "Focus on deep work flow, the hum of the grinder as white noise, and reliable sockets.",
        "Couples": "Focus on the clink of spoons, soft shadows, and a sanctuary from the outside world.",
        "Coffee Geeks": "Focus on extraction, bean processing notes (acidity/body), and precision brewing.",
        "Families": "Focus on easy mornings, no-spill cups, and sugar-dusted smiles.",
        "General": "Focus on urban sanctuary vibes and high-quality hospitality."
    }

    # Исправленная логика настроения
    if data.mood.lower() in ["witty", "остроумный", "шутливый"]:
        mood_instr = (
            "Tone: Witty. Use the 'Expectation vs Reality' trope. "
            "Focus on the irony: your brain wants sleep, but your boss wants the report. "
            "Be a bit edgy. Avoid 'we are here for you' – instead use 'we have the caffeine you clearly need'."
        )
    else:
        # Стандартное поведение для других настроений
        mood_instr = f"Tone: {data.mood}. Style: Professional and engaging."

    trigger = audience_triggers.get(target, audience_triggers["General"])
    event_ctx = f"\n### PROMO EVENT (MUST INTEGRATE): {event}" if event.strip() else ""

    prompt = (
        f"You are a Senior Copywriter for '{data.cafe_name}'. {mood_instr}\n"
        f"Language: {data.language}. Context: {data.weather} weather, {data.time}. Audience: {target}.\n"
        f"Strategy: {trigger}{event_ctx}\n\n"
        
        f"TASK: Write EXACTLY {count} Instagram post(s). No intro, no conversational filler.\n\n"
        
        "STRICT FORMATTING RULES (MANDATORY):\n"
        "For EACH post, use this EXACT structure:\n"
        "[Write the caption here] | [Write the photo description here]\n"
        "--- (Separator only between posts)\n\n"
        
        "EXAMPLE:\n"
        "Best coffee in town! | A close-up shot of a latte with heart art.\n"
        
        "CONSTRAINTS:\n"
        "- Use sensory marketing: describe smells, sounds, and textures.\n"
        "- No 'whispering winds' or 'dancing shadows' unless in Poetic mood.\n"
        "- Max 2 emojis per post.\n"
        f"- Output strictly in {data.language}."
    )
    return prompt

# --- ENDPOINTS ---
@app.get("/logo.png")
async def get_logo():
    # Ищем файл в корне проекта
    file_path = "logo.png"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    
    # Если не нашли в корне, попробуем в папке static
    static_path = os.path.join("static", "logo.png")
    if os.path.exists(static_path):
        return FileResponse(static_path, media_type="image/png")
        
    return {"error": "File not found"}

@app.get("/get-credits")
def get_credits(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, credits=3, is_premium=False)
        db.add(user); db.commit(); db.refresh(user)
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
    DOMAIN = "https://cafecaption.com/"
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
