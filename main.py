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
# --- ТВОЯ ГЕНЕРАЦИЯ ---
@app.post("/generate")
async def generate(data: GenerateRequest):
    texts = []
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """
Ты — профессиональный креативный копирайтер и сторителлер,
который много лет пишет живые тексты для кафе и кофеен.

Ты создаёшь тексты, которые выглядят как написанные человеком,
а не ИИ.

Жёсткие правила:
- никакой прямой рекламы
- никаких шаблонов и маркетинговых клише
- естественный, разговорный язык
- возможна лёгкая неидеальность и смена ритма
- каждый текст должен отличаться по структуре и подаче

Запрещено использовать:
«уютная атмосфера», «идеальное место», «ждём вас», «приглашаем»
списки преимуществ и объяснения.
"""

    opening_styles = [
        "начни с вопроса",
        "начни с короткой мысли или внутреннего комментария",
        "начни с образа или ощущения",
        "начни с наблюдения за людьми или моментом",
        "начни с фразы с середины мысли"
    ]

    for i in range(data.variants):
        previous_texts = "\n".join(texts) if texts else "—"

        user_prompt = f"""
Контекст: кафе.
От чьего лица: {data.speaker}.
Настроение: {data.mood}.
Повод / ситуация: {data.occasion}.

Стиль начала: {opening_styles[i % len(opening_styles)]}.

Ранее сгенерированные тексты:
{previous_texts}

Требования:
- новый текст НЕ должен повторять лексику, образы или структуру предыдущих
- другая подача и другой ритм
- 1–3 коротких абзаца или одна ёмкая мысль
- без хэштегов, без эмодзи, без объяснений
"""

        try:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 1.2,
                "max_tokens": 100
            }

            response = requests.post(URL, headers=headers, json=payload, timeout=10)

            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content'].strip()
                texts.append(text)
            else:
                texts.append(f"Groq Error {response.status_code}")

        except Exception:
            texts.append("Connection Error")

    return {"texts": texts}
